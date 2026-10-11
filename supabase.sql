-- Paste into Supabase → SQL Editor (project poshan-app) and Run. Enables phone-to-phone sync.
create table if not exists public.lt_events (
  household text not null, id uuid not null, type text not null,
  start_ts bigint not null, end_ts bigint, data jsonb not null default '{}'::jsonb,
  deleted boolean not null default false, updated bigint not null,
  synced_at timestamptz not null default now(), primary key (household, id)
);
create index if not exists lt_events_household_synced on public.lt_events (household, synced_at);
alter table public.lt_events enable row level security;
revoke all on public.lt_events from anon, authenticated;

create or replace function public.lt_push(p_key text, p_events jsonb)
returns void language plpgsql security definer set search_path = public as $$
begin
  if p_key is null or length(p_key) < 16 then raise exception 'bad key'; end if;
  insert into lt_events (household, id, type, start_ts, end_ts, data, deleted, updated, synced_at)
  select p_key, (e->>'id')::uuid, e->>'type', (e->>'start_ts')::bigint, nullif(e->>'end_ts','')::bigint,
         coalesce(e->'data','{}'::jsonb), coalesce((e->>'deleted')::boolean,false), (e->>'updated')::bigint, clock_timestamp()
  from jsonb_array_elements(p_events) e
  on conflict (household, id) do update set
    type = excluded.type, start_ts = excluded.start_ts, end_ts = excluded.end_ts, data = excluded.data,
    deleted = excluded.deleted, updated = excluded.updated, synced_at = clock_timestamp()
  where excluded.updated >= lt_events.updated;
end $$;

create or replace function public.lt_pull(p_key text, p_since timestamptz)
returns setof public.lt_events language sql security definer set search_path = public stable as $$
  select * from lt_events
  where household = p_key and length(p_key) >= 16
    and synced_at > coalesce(p_since, 'epoch'::timestamptz)
  order by synced_at;
$$;

revoke all on function public.lt_push(text, jsonb) from public;
revoke all on function public.lt_pull(text, timestamptz) from public;
grant execute on function public.lt_push(text, jsonb) to anon;
grant execute on function public.lt_pull(text, timestamptz) to anon;
