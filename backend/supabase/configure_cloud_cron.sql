\set ON_ERROR_STOP on

create extension if not exists pg_cron;
create extension if not exists pg_net with schema extensions;
create extension if not exists supabase_vault cascade;

delete from vault.secrets
where name in ('pulse_api_url', 'pulse_job_secret');

select vault.create_secret(
  :'api_url',
  'pulse_api_url',
  'Render API base URL'
);
select vault.create_secret(
  :'job_secret',
  'pulse_job_secret',
  'Pulse cloud job secret'
);

create or replace function public.invoke_pulse_job(job_path text)
returns bigint
language plpgsql
security definer
set search_path = ''
as $$
declare
  api_url text;
  job_secret text;
  request_id bigint;
begin
  select decrypted_secret
  into api_url
  from vault.decrypted_secrets
  where name = 'pulse_api_url'
  order by created_at desc
  limit 1;

  select decrypted_secret
  into job_secret
  from vault.decrypted_secrets
  where name = 'pulse_job_secret'
  order by created_at desc
  limit 1;

  if api_url is null or job_secret is null then
    raise exception 'Pulse cloud secrets are not configured';
  end if;

  select net.http_post(
    url := rtrim(api_url, '/') || '/jobs/' || ltrim(job_path, '/'),
    headers := jsonb_build_object(
      'Content-Type',
      'application/json',
      'X-Job-Secret',
      job_secret
    ),
    body := '{}'::jsonb,
    timeout_milliseconds := 150000
  )
  into request_id;

  return request_id;
end;
$$;

revoke all on function public.invoke_pulse_job(text) from public;
grant execute on function public.invoke_pulse_job(text) to postgres;

select cron.unschedule(jobid)
from cron.job
where jobname like 'pulse-%';

-- Supabase Cron uses UTC. These heartbeat jobs keep Render warm from
-- 06:00 through 22:00 Asia/Kolkata, then allow its 15-minute idle sleep.
select cron.schedule(
  'pulse-heartbeat-opening',
  '30,40,50 0 * * *',
  $$select public.invoke_pulse_job('heartbeat')$$
);
select cron.schedule(
  'pulse-heartbeat-daytime',
  '*/10 1-15 * * *',
  $$select public.invoke_pulse_job('heartbeat')$$
);
select cron.schedule(
  'pulse-heartbeat-closing',
  '0,10,20,30 16 * * *',
  $$select public.invoke_pulse_job('heartbeat')$$
);

select cron.schedule(
  'pulse-ingest',
  '35 0,2,4,6,8,10,12,14,15 * * *',
  $$select public.invoke_pulse_job('ingest')$$
);
select cron.schedule(
  'pulse-gmail',
  '40 0,4,8,12,15 * * *',
  $$select public.invoke_pulse_job('gmail')$$
);
select cron.schedule(
  'pulse-enrich',
  '50 0-15 * * *',
  $$select public.invoke_pulse_job('enrich')$$
);
select cron.schedule(
  'pulse-reembed',
  '55 0-15/2 * * *',
  $$select public.invoke_pulse_job('reembed')$$
);
select cron.schedule(
  'pulse-trends',
  '45 0 * * *',
  $$select public.invoke_pulse_job('trends')$$
);
select cron.schedule(
  'pulse-digest',
  '0 1 * * *',
  $$select public.invoke_pulse_job('digest')$$
);
select cron.schedule(
  'pulse-retention',
  '10 1 * * 0',
  $$select public.invoke_pulse_job('retention')$$
);
