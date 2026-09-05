drop policy if exists "travel blog public documents read" on public.travel_blog_documents;
create policy "travel blog public documents read" on public.travel_blog_documents
for select to anon using (key in ('posts','locations','site_theme'));

drop policy if exists "travel blog admin documents read" on public.travel_blog_documents;
create policy "travel blog admin documents read" on public.travel_blog_documents
for select to authenticated using (((select auth.jwt()) ->> 'email') = 'cutealbert61@gmail.com');
drop policy if exists "travel blog admin documents insert" on public.travel_blog_documents;
create policy "travel blog admin documents insert" on public.travel_blog_documents
for insert to authenticated with check (((select auth.jwt()) ->> 'email') = 'cutealbert61@gmail.com');
drop policy if exists "travel blog admin documents update" on public.travel_blog_documents;
create policy "travel blog admin documents update" on public.travel_blog_documents
for update to authenticated
using (((select auth.jwt()) ->> 'email') = 'cutealbert61@gmail.com')
with check (((select auth.jwt()) ->> 'email') = 'cutealbert61@gmail.com');
drop policy if exists "travel blog admin documents delete" on public.travel_blog_documents;
create policy "travel blog admin documents delete" on public.travel_blog_documents
for delete to authenticated using (((select auth.jwt()) ->> 'email') = 'cutealbert61@gmail.com');

drop policy if exists "travel blog media manifest public read" on public.travel_blog_media;
create policy "travel blog media manifest public read" on public.travel_blog_media
for select to anon using (true);
drop policy if exists "travel blog admin media manage" on public.travel_blog_media;
create policy "travel blog admin media manage" on public.travel_blog_media
for all to authenticated
using (((select auth.jwt()) ->> 'email') = 'cutealbert61@gmail.com')
with check (((select auth.jwt()) ->> 'email') = 'cutealbert61@gmail.com');
drop policy if exists "travel blog admin releases manage" on public.travel_blog_releases;
create policy "travel blog admin releases manage" on public.travel_blog_releases
for all to authenticated
using (((select auth.jwt()) ->> 'email') = 'cutealbert61@gmail.com')
with check (((select auth.jwt()) ->> 'email') = 'cutealbert61@gmail.com');

drop policy if exists "travel blog admin media upload" on storage.objects;
create policy "travel blog admin media upload" on storage.objects
for insert to authenticated with check (
  bucket_id='travel-blog-media' and ((select auth.jwt()) ->> 'email')='cutealbert61@gmail.com'
);
drop policy if exists "travel blog admin media update" on storage.objects;
create policy "travel blog admin media update" on storage.objects
for update to authenticated
using (bucket_id='travel-blog-media' and ((select auth.jwt()) ->> 'email')='cutealbert61@gmail.com')
with check (bucket_id='travel-blog-media' and ((select auth.jwt()) ->> 'email')='cutealbert61@gmail.com');
drop policy if exists "travel blog admin media delete" on storage.objects;
create policy "travel blog admin media delete" on storage.objects
for delete to authenticated
using (bucket_id='travel-blog-media' and ((select auth.jwt()) ->> 'email')='cutealbert61@gmail.com');

drop policy if exists "travel blog admin backups read" on storage.objects;
create policy "travel blog admin backups read" on storage.objects
for select to authenticated
using (bucket_id='travel-blog-backups' and ((select auth.jwt()) ->> 'email')='cutealbert61@gmail.com');
drop policy if exists "travel blog admin backups insert" on storage.objects;
create policy "travel blog admin backups insert" on storage.objects
for insert to authenticated with check (
  bucket_id='travel-blog-backups' and ((select auth.jwt()) ->> 'email')='cutealbert61@gmail.com'
);
drop policy if exists "travel blog admin backups update" on storage.objects;
create policy "travel blog admin backups update" on storage.objects
for update to authenticated
using (bucket_id='travel-blog-backups' and ((select auth.jwt()) ->> 'email')='cutealbert61@gmail.com')
with check (bucket_id='travel-blog-backups' and ((select auth.jwt()) ->> 'email')='cutealbert61@gmail.com');
drop policy if exists "travel blog admin backups delete" on storage.objects;
create policy "travel blog admin backups delete" on storage.objects
for delete to authenticated
using (bucket_id='travel-blog-backups' and ((select auth.jwt()) ->> 'email')='cutealbert61@gmail.com');
