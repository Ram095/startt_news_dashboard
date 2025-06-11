# scripts/init_db.sql
-- Database initialization script for PostgreSQL

-- Create database (run this as superuser)
-- CREATE DATABASE news_dashboard;
-- CREATE USER news_user WITH PASSWORD 'your_password';
-- GRANT ALL PRIVILEGES ON DATABASE news_dashboard TO news_user;

-- Connect to news_dashboard database and run the rest

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create schemas
CREATE SCHEMA IF NOT EXISTS analytics;
CREATE SCHEMA IF NOT EXISTS monitoring;

-- Articles table (main table created by application)
-- Additional indexes for performance
CREATE INDEX IF NOT EXISTS idx_articles_title_trgm ON articles USING gin (title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_articles_description_trgm ON articles USING gin (description gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_articles_quality_score ON articles (quality_score DESC);
CREATE INDEX IF NOT EXISTS idx_articles_sentiment_score ON articles (sentiment_score);

-- Analytics views
CREATE OR REPLACE VIEW analytics.daily_article_stats AS
SELECT 
    DATE(created_at) as date,
    source,
    COUNT(*) as article_count,
    AVG(quality_score) as avg_quality,
    AVG(sentiment_score) as avg_sentiment
FROM articles 
GROUP BY DATE(created_at), source
ORDER BY date DESC;

CREATE OR REPLACE VIEW analytics.source_performance AS
SELECT 
    source,
    COUNT(*) as total_articles,
    AVG(quality_score) as avg_quality,
    COUNT(CASE WHEN status = 'published' THEN 1 END) as published_count,
    COUNT(CASE WHEN status = 'rejected' THEN 1 END) as rejected_count,
    ROUND(
        COUNT(CASE WHEN status = 'published' THEN 1 END)::NUMERIC / 
        NULLIF(COUNT(*), 0) * 100, 2
    ) as publish_rate
FROM articles 
GROUP BY source;

-- Monitoring tables
CREATE TABLE IF NOT EXISTS monitoring.system_metrics (
    id SERIAL PRIMARY KEY,
    metric_name TEXT NOT NULL,
    metric_value NUMERIC NOT NULL,
    metric_unit TEXT,
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS monitoring.error_logs (
    id SERIAL PRIMARY KEY,
    error_type TEXT NOT NULL,
    error_message TEXT NOT NULL,
    stack_trace TEXT,
    context JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for monitoring
CREATE INDEX IF NOT EXISTS idx_system_metrics_name_time ON monitoring.system_metrics (metric_name, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_error_logs_type_time ON monitoring.error_logs (error_type, created_at DESC);

-- Functions for analytics
CREATE OR REPLACE FUNCTION analytics.get_article_trends(days INTEGER DEFAULT 30)
RETURNS TABLE (
    date DATE,
    total_articles BIGINT,
    avg_quality NUMERIC,
    top_source TEXT
) AS $$
BEGIN
    RETURN QUERY
    WITH daily_stats AS (
        SELECT 
            DATE(created_at) as article_date,
            COUNT(*) as count,
            AVG(quality_score) as quality,
            MODE() WITHIN GROUP (ORDER BY source) as top_src
        FROM articles 
        WHERE created_at >= CURRENT_DATE - days
        GROUP BY DATE(created_at)
    )
    SELECT 
        article_date,
        count,
        ROUND(quality, 2),
        top_src
    FROM daily_stats
    ORDER BY article_date DESC;
END;
$$ LANGUAGE plpgsql;

-- Cleanup function for old data
CREATE OR REPLACE FUNCTION cleanup_old_data(retention_days INTEGER DEFAULT 365)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM monitoring.system_metrics 
    WHERE recorded_at < CURRENT_DATE - retention_days;
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    
    DELETE FROM monitoring.error_logs 
    WHERE created_at < CURRENT_DATE - retention_days;
    
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Create user roles
CREATE ROLE news_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO news_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO news_reader;

CREATE ROLE news_writer;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO news_writer;
GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO news_writer;

-- Grant permissions to application user
-- GRANT news_writer TO news_user;

COMMIT;