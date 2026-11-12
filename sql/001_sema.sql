-- Ajan Ofisi SaaS veritabani (Supabase Postgres). Supabase SQL Editor'de bir kez calistirin.
-- Musteri yalitimi: her tabloda musteri_id + RLS. Tarayici yalnizca kendi uyesi oldugu musterinin
-- satirlarini OKUYABILIR; tum yazmalar sunucudan (service role) gecer ve sunucu uyeligi ayrica dogrular.

create table if not exists musteriler (
  id            text primary key check (id ~ '^[a-z0-9][a-z0-9_-]{0,62}$'),
  ad            text not null,
  profil        jsonb not null,                       -- ofis/ ajanlarinin profil.json'u
  yayin_ayar    jsonb not null default '{}'::jsonb,   -- otomatik yayin, saatler, mesai
  durum         text not null default 'deneme' check (durum in ('deneme','aktif','duraklatildi','kapali')),
  deneme_bitis  timestamptz,
  meta_bilgi    jsonb not null default '{}'::jsonb,   -- sayfa adi/id, IG kullanici adi (gizli degil)
  meta_token    text,                                 -- SIFRELI sayfa anahtari (Fernet); duz metin asla
  meta_aday     text,                                 -- SIFRELI: OAuth sonrasi secilecek sayfalar
  son_uretim    date,
  olusturma     timestamptz not null default now(),
  guncelleme    timestamptz not null default now()
);

create table if not exists uyelikler (
  kullanici_id  uuid not null,                        -- auth.users.id
  musteri_id    text not null references musteriler(id) on delete cascade,
  rol           text not null default 'sahip' check (rol in ('sahip','editor','izleyici')),
  eposta        text,
  primary key (kullanici_id, musteri_id)
);

create table if not exists icerikler (
  musteri_id    text not null references musteriler(id) on delete cascade,
  klasor        text not null,
  tur           text,                                 -- post | carousel | reels
  meta          jsonb not null default '{}'::jsonb,   -- ajanlarin meta.json'u
  yayin         jsonb not null default '{}'::jsonb,   -- yayin.json: durum, hedefler, zaman, sonuc
  caption       text not null default '',
  ekler         jsonb not null default '{}'::jsonb,   -- kucuk metin dosyalari (taslak, rapor, performans)
  dosyalar      text[] not null default '{}',         -- depodaki gorsel/video dosya adlari
  surum         integer not null default 1,           -- iyimser kilit: web ve isci ayni anda yazarsa
  olusturma     timestamptz not null default now(),
  guncelleme    timestamptz not null default now(),
  primary key (musteri_id, klasor)
);
create index if not exists icerikler_sira on icerikler (musteri_id, klasor desc);

create table if not exists isler (
  id            uuid primary key default gen_random_uuid(),
  musteri_id    text not null references musteriler(id) on delete cascade,
  tur           text not null check (tur in ('uret','yayin_turu','kaldir','revize','plan')),
  parametre     jsonb not null default '{}'::jsonb,
  durum         text not null default 'bekliyor' check (durum in ('bekliyor','calisiyor','bitti','hata')),
  deneme        integer not null default 0,
  isci          text,
  kayit         text,
  olusturma     timestamptz not null default now(),
  baslama       timestamptz,
  bitis         timestamptz
);
create index if not exists isler_sira on isler (durum, olusturma);
create index if not exists isler_musteri on isler (musteri_id, olusturma desc);

create table if not exists pano (
  id            bigint generated always as identity primary key,
  musteri_id    text not null references musteriler(id) on delete cascade,
  zaman         timestamptz not null default now(),
  gonderen      text, alici text, tur text, icerik text
);
create index if not exists pano_musteri on pano (musteri_id, id desc);

-- ---------------- is kuyrugu: atomik is alma ----------------
-- Ayni musteride ayni anda tek is calisir (veri klasoru tek yazara ait). 'calisiyor'da takili kalan
-- (isci coktu) is 'zaman_asimi_dk' sonra yeniden alinabilir.
create or replace function is_al(isci_adi text, zaman_asimi_dk integer default 60)
returns setof isler language plpgsql security definer set search_path = public as $$
declare secilen uuid;
begin
  update isler set durum = 'bekliyor', kayit = coalesce(kayit,'') || ' [zaman asimi, yeniden kuyrukta]'
   where durum = 'calisiyor' and baslama < now() - make_interval(mins => zaman_asimi_dk) and deneme < 3;
  select i.id into secilen from isler i
   where i.durum = 'bekliyor'
     and not exists (select 1 from isler c where c.musteri_id = i.musteri_id and c.durum = 'calisiyor')
   order by i.olusturma
   for update skip locked limit 1;
  if secilen is null then return; end if;
  return query update isler set durum = 'calisiyor', isci = isci_adi, baslama = now(), deneme = deneme + 1
                where id = secilen returning *;
end $$;

-- ---------------- RLS: musteri yalitimi ----------------
alter table musteriler enable row level security;
alter table uyelikler  enable row level security;
alter table icerikler  enable row level security;
alter table isler      enable row level security;
alter table pano       enable row level security;

create or replace function uye_mi(m text) returns boolean language sql stable security definer
set search_path = public as $$
  select exists (select 1 from uyelikler u where u.musteri_id = m and u.kullanici_id = auth.uid())
$$;

drop policy if exists uye_okur on uyelikler;
create policy uye_okur on uyelikler for select using (kullanici_id = auth.uid());
drop policy if exists uye_okur on icerikler;
create policy uye_okur on icerikler for select using (uye_mi(musteri_id));
drop policy if exists uye_okur on isler;
create policy uye_okur on isler for select using (uye_mi(musteri_id));
drop policy if exists uye_okur on pano;
create policy uye_okur on pano for select using (uye_mi(musteri_id));
-- musteriler tablosu tarayiciya kapali (sifreli token kolonlari var); profil sunucudan okunur.

revoke all on function is_al(text, integer) from public, anon, authenticated;

-- ---------------- dosya deposu ----------------
-- Supabase Storage > New bucket: "ajan-ofisi", Public KAPALI. Dosyalar sunucudan imzali adresle verilir.
