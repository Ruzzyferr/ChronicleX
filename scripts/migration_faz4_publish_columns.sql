-- Mevcut PostgreSQL veritabanına Faz 4 sütunları (bir kez çalıştırın)
ALTER TABLE published_videos ADD COLUMN IF NOT EXISTS youtube_video_id VARCHAR(128);
ALTER TABLE published_videos ADD COLUMN IF NOT EXISTS tiktok_publish_id VARCHAR(128);
ALTER TABLE published_videos ADD COLUMN IF NOT EXISTS instagram_media_id VARCHAR(128);
ALTER TABLE published_videos ADD COLUMN IF NOT EXISTS publish_queue_status VARCHAR(32);
