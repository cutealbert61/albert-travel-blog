alter table public.travel_blog_media
drop constraint if exists travel_blog_media_pkey;

alter table public.travel_blog_media
add constraint travel_blog_media_pkey primary key (source_url);

alter table public.travel_blog_media
drop constraint if exists travel_blog_media_source_url_key;

create index if not exists travel_blog_media_object_path_idx
on public.travel_blog_media(object_path);
