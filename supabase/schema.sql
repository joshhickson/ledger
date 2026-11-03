-- Shared ledger on Supabase: one record for all of the owner's Claude Code sessions, local and cloud.
--
-- Run this once in a new Supabase project (SQL editor, or `supabase db push`). It is safe to re-run.
--
-- Who can read or write: only a caller holding a ledger token. The tables live in the schema `ledger`, which the
-- Supabase Data API doesn't expose, with row-level security on and no policies, so the project's public
-- (publishable / anon) key can't touch them. The only way in is the two functions below, and each one first checks
-- the token. Tokens are stored as SHA-256 hashes; `ledger.py new-token LABEL` makes one and prints the line that
-- registers it. To cut a token off: update ledger.tokens set revoked_at = now() where label = 'LABEL';
--
-- The token travels in the request body (p_token) or in an `x-ledger-token` header, so a proxy can add it for a
-- cloud session without the session ever holding it.

create schema if not exists ledger;
revoke all on schema ledger from public, anon, authenticated;

create table if not exists ledger.items(
  id text primary key, project text not null default 'main', kind text not null, title text not null,
  body text not null default '', quote text not null default '', source text not null default '',
  who text not null default 'claude', basis text not null default '', status text not null default 'open',
  owner text not null default '', priority integer not null default 2, tags text not null default '',
  created text not null, updated text not null,
  pushed_at timestamptz not null default now(), pushed_by text);
create table if not exists ledger.links(
  src text not null, rel text not null, dst text not null, note text not null default '', created text not null default '',
  pushed_at timestamptz not null default now(), pushed_by text, primary key(src, rel, dst));
create table if not exists ledger.events(
  seq bigserial primary key, ts text not null, action text not null, item text, detail text, project text,
  pushed_at timestamptz not null default now(), pushed_by text);
create table if not exists ledger.state(
  key text primary key, value text, updated text, pushed_at timestamptz not null default now(), pushed_by text);
create table if not exists ledger.tokens(
  label text primary key, hash text not null unique, created timestamptz not null default now(),
  revoked_at timestamptz, last_used timestamptz);

alter table ledger.items enable row level security;
alter table ledger.links enable row level security;
alter table ledger.events enable row level security;
alter table ledger.state enable row level security;
alter table ledger.tokens enable row level security;
revoke all on all tables in schema ledger from public, anon, authenticated;
revoke all on all sequences in schema ledger from public, anon, authenticated;

-- The caller's token label, or an error. Not callable from outside.
create or replace function ledger.check_token(p_token text) returns text
language plpgsql security definer set search_path = '' as $$
declare
  tok text := coalesce(nullif(p_token, ''),
                       nullif(current_setting('request.headers', true), '')::json ->> 'x-ledger-token', '');
  who text;
begin
  update ledger.tokens set last_used = now()
   where hash = encode(sha256(convert_to(tok, 'UTF8')), 'hex') and revoked_at is null
  returning label into who;
  if who is null then
    raise exception 'ledger: token not recognised' using errcode = '28000';
  end if;
  return who;
end $$;
revoke all on function ledger.check_token(text) from public, anon, authenticated;

-- Everything but the event log: items, links, state.
create or replace function public.ledger_pull(p_token text default '') returns jsonb
language plpgsql security definer set search_path = '' as $$
declare caller text := ledger.check_token(p_token);
begin
  return jsonb_build_object(
    'items', coalesce((select jsonb_agg(to_jsonb(i) - 'pushed_at' - 'pushed_by') from ledger.items i), '[]'),
    'links', coalesce((select jsonb_agg(to_jsonb(l) - 'pushed_at' - 'pushed_by') from ledger.links l), '[]'),
    'state', coalesce((select jsonb_agg(to_jsonb(s) - 'pushed_at' - 'pushed_by') from ledger.state s), '[]'),
    'by', caller, 'server_time', now());
end $$;

-- One session's changes. p_batch: {project, items: [...], links: [...], events: [...], state: [...]}.
-- A new item ("_new": true) whose ID another session already took gets the next free ID; the answer lists each
-- rename as {"old": "new"}, and the batch's links, events and focus follow it. An edit sends only the fields it
-- changed, so two sessions changing different fields of one item don't undo each other.
create or replace function public.ledger_push(p_batch jsonb, p_token text default '') returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  caller text := ledger.check_token(p_token);
  it jsonb; ln jsonb; ev jsonb; st jsonb;
  nid text; pfx text; renamed jsonb := '{}'; missing jsonb := '[]';
  n_items int := 0; n_links int := 0; n_events int := 0; n_state int := 0;
begin
  perform pg_advisory_xact_lock(hashtext('ledger_push'));  -- one push at a time: new IDs can't collide
  for it in select * from jsonb_array_elements(coalesce(p_batch -> 'items', '[]')) loop
    nid := it ->> 'id';
    if coalesce((it ->> '_new')::boolean, false) then
      if exists (select 1 from ledger.items where id = nid) then
        pfx := substring(nid from '^[A-Za-z]+');
        select pfx || (coalesce(max(substring(id from '[0-9]+$')::int), 0) + 1) into nid
          from ledger.items where id ~ ('^' || pfx || '[0-9]+$');
        renamed := renamed || jsonb_build_object(it ->> 'id', nid);
      end if;
      insert into ledger.items(id, project, kind, title, body, quote, source, who, basis, status, owner, priority,
                               tags, created, updated, pushed_by)
      values (nid, coalesce(it ->> 'project', 'main'), it ->> 'kind', it ->> 'title', coalesce(it ->> 'body', ''),
              coalesce(it ->> 'quote', ''), coalesce(it ->> 'source', ''), coalesce(it ->> 'who', 'claude'),
              coalesce(it ->> 'basis', ''), coalesce(it ->> 'status', 'open'), coalesce(it ->> 'owner', ''),
              coalesce((it ->> 'priority')::int, 2), coalesce(it ->> 'tags', ''), it ->> 'created', it ->> 'updated',
              caller);
    else
      nid := coalesce(renamed ->> nid, nid);
      update ledger.items set
        project = case when it ? 'project' then it ->> 'project' else project end,
        kind = case when it ? 'kind' then it ->> 'kind' else kind end,
        title = case when it ? 'title' then it ->> 'title' else title end,
        body = case when it ? 'body' then it ->> 'body' else body end,
        quote = case when it ? 'quote' then it ->> 'quote' else quote end,
        source = case when it ? 'source' then it ->> 'source' else source end,
        who = case when it ? 'who' then it ->> 'who' else who end,
        basis = case when it ? 'basis' then it ->> 'basis' else basis end,
        status = case when it ? 'status' then it ->> 'status' else status end,
        owner = case when it ? 'owner' then it ->> 'owner' else owner end,
        priority = case when it ? 'priority' then (it ->> 'priority')::int else priority end,
        tags = case when it ? 'tags' then it ->> 'tags' else tags end,
        updated = case when it ? 'updated' then it ->> 'updated' else updated end,
        pushed_at = now(), pushed_by = caller
      where id = nid;
      if not found then
        missing := missing || to_jsonb(nid);
      end if;
    end if;
    n_items := n_items + 1;
  end loop;
  for ln in select * from jsonb_array_elements(coalesce(p_batch -> 'links', '[]')) loop
    insert into ledger.links(src, rel, dst, note, created, pushed_by)
    values (coalesce(renamed ->> (ln ->> 'src'), ln ->> 'src'), ln ->> 'rel',
            coalesce(renamed ->> (ln ->> 'dst'), ln ->> 'dst'), coalesce(ln ->> 'note', ''),
            coalesce(ln ->> 'created', ''), caller)
    on conflict (src, rel, dst) do update set note = excluded.note, created = excluded.created,
                                              pushed_at = now(), pushed_by = caller;
    n_links := n_links + 1;
  end loop;
  for ev in select * from jsonb_array_elements(coalesce(p_batch -> 'events', '[]')) loop
    insert into ledger.events(ts, action, item, detail, project, pushed_by)
    values (ev ->> 'ts', ev ->> 'action', coalesce(renamed ->> (ev ->> 'item'), ev ->> 'item'), ev ->> 'detail',
            coalesce(ev ->> 'project', p_batch ->> 'project'), caller);
    n_events := n_events + 1;
  end loop;
  for st in select * from jsonb_array_elements(coalesce(p_batch -> 'state', '[]')) loop
    insert into ledger.state(key, value, updated, pushed_by)
    values (st ->> 'key', coalesce(renamed ->> (st ->> 'value'), st ->> 'value'), st ->> 'updated', caller)
    on conflict (key) do update set value = excluded.value, updated = excluded.updated,
                                    pushed_at = now(), pushed_by = caller;
    n_state := n_state + 1;
  end loop;
  return jsonb_build_object('renamed', renamed, 'missing', missing, 'by', caller,
                            'counts', jsonb_build_object('items', n_items, 'links', n_links,
                                                         'events', n_events, 'state', n_state));
end $$;

revoke all on function public.ledger_pull(text) from public, anon, authenticated;
revoke all on function public.ledger_push(jsonb, text) from public, anon, authenticated;
grant execute on function public.ledger_pull(text) to anon, authenticated;
grant execute on function public.ledger_push(jsonb, text) to anon, authenticated;
