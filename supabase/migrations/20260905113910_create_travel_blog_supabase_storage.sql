create table if not exists public.travel_blog_documents (
  key text primary key,
  payload jsonb not null,
  updated_at timestamptz not null default now(),
  updated_by uuid null references auth.users(id),
  constraint travel_blog_documents_key_check
    check (key in ('posts','history','week_plan','locations','site_theme'))
);

create table if not exists public.travel_blog_media (
  object_path text primary key,
  source_url text not null unique,
  content_type text,
  size_bytes bigint not null default 0 check (size_bytes >= 0),
  sha256 text,
  width integer,
  height integer,
  migrated_at timestamptz not null default now(),
  metadata jsonb not null default '{}'::jsonb
);

create table if not exists public.travel_blog_releases (
  id uuid primary key default gen_random_uuid(),
  version_label text not null unique,
  commit_sha text,
  archive_path text not null unique,
  file_count integer not null default 0 check (file_count >= 0),
  size_bytes bigint not null default 0 check (size_bytes >= 0),
  sha256 text,
  manifest jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

alter table public.travel_blog_documents enable row level security;
alter table public.travel_blog_media enable row level security;
alter table public.travel_blog_releases enable row level security;

grant select on public.travel_blog_documents to anon, authenticated;
grant insert, update, delete on public.travel_blog_documents to authenticated;
grant select on public.travel_blog_media to anon, authenticated;
grant insert, update, delete on public.travel_blog_media to authenticated;
grant select, insert, update, delete on public.travel_blog_releases to authenticated;

create policy "travel blog public documents read" on public.travel_blog_documents
for select to anon, authenticated using (key in ('posts','locations','site_theme'));
create policy "travel blog admin documents read" on public.travel_blog_documents
for select to authenticated using ((select auth.jwt() ->> 'email') = 'cutealbert61@gmail.com');
create policy "travel blog admin documents insert" on public.travel_blog_documents
for insert to authenticated with check ((select auth.jwt() ->> 'email') = 'cutealbert61@gmail.com');
create policy "travel blog admin documents update" on public.travel_blog_documents
for update to authenticated
using ((select auth.jwt() ->> 'email') = 'cutealbert61@gmail.com')
with check ((select auth.jwt() ->> 'email') = 'cutealbert61@gmail.com');
create policy "travel blog admin documents delete" on public.travel_blog_documents
for delete to authenticated using ((select auth.jwt() ->> 'email') = 'cutealbert61@gmail.com');
create policy "travel blog media manifest public read" on public.travel_blog_media
for select to anon, authenticated using (true);
create policy "travel blog admin media manage" on public.travel_blog_media
for all to authenticated
using ((select auth.jwt() ->> 'email') = 'cutealbert61@gmail.com')
with check ((select auth.jwt() ->> 'email') = 'cutealbert61@gmail.com');
create policy "travel blog admin releases manage" on public.travel_blog_releases
for all to authenticated
using ((select auth.jwt() ->> 'email') = 'cutealbert61@gmail.com')
with check ((select auth.jwt() ->> 'email') = 'cutealbert61@gmail.com');

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values
  ('travel-blog-media','travel-blog-media',true,20971520,array['image/jpeg','image/png','image/webp','image/gif']),
  ('travel-blog-backups','travel-blog-backups',false,524288000,array['application/zip','application/x-zip-compressed','application/octet-stream','application/x-git-bundle'])
on conflict (id) do update set
  public=excluded.public,
  file_size_limit=excluded.file_size_limit,
  allowed_mime_types=excluded.allowed_mime_types;

create policy "travel blog admin media upload" on storage.objects
for insert to authenticated with check (
  bucket_id='travel-blog-media' and (select auth.jwt() ->> 'email')='cutealbert61@gmail.com'
);
create policy "travel blog admin media update" on storage.objects
for update to authenticated
using (bucket_id='travel-blog-media' and (select auth.jwt() ->> 'email')='cutealbert61@gmail.com')
with check (bucket_id='travel-blog-media' and (select auth.jwt() ->> 'email')='cutealbert61@gmail.com');
create policy "travel blog admin media delete" on storage.objects
for delete to authenticated
using (bucket_id='travel-blog-media' and (select auth.jwt() ->> 'email')='cutealbert61@gmail.com');
create policy "travel blog admin backups read" on storage.objects
for select to authenticated
using (bucket_id='travel-blog-backups' and (select auth.jwt() ->> 'email')='cutealbert61@gmail.com');
create policy "travel blog admin backups insert" on storage.objects
for insert to authenticated with check (
  bucket_id='travel-blog-backups' and (select auth.jwt() ->> 'email')='cutealbert61@gmail.com'
);
create policy "travel blog admin backups update" on storage.objects
for update to authenticated
using (bucket_id='travel-blog-backups' and (select auth.jwt() ->> 'email')='cutealbert61@gmail.com')
with check (bucket_id='travel-blog-backups' and (select auth.jwt() ->> 'email')='cutealbert61@gmail.com');
create policy "travel blog admin backups delete" on storage.objects
for delete to authenticated
using (bucket_id='travel-blog-backups' and (select auth.jwt() ->> 'email')='cutealbert61@gmail.com');
