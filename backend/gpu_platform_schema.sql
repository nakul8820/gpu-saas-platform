-- =============================================================================
-- GPU-AS-A-SERVICE PLATFORM — FULL POSTGRESQL SCHEMA
-- =============================================================================
-- Run order: enums → extensions → tables → indexes → triggers → views
-- Tested on PostgreSQL 15+
-- =============================================================================


-- -----------------------------------------------------------------------------
-- EXTENSIONS
-- -----------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "pgcrypto";       -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "pg_trgm";        -- fuzzy search on emails/names
CREATE EXTENSION IF NOT EXISTS "btree_gist";     -- exclusion constraints


-- -----------------------------------------------------------------------------
-- ENUMS
-- -----------------------------------------------------------------------------

CREATE TYPE user_role AS ENUM (
    'user',        -- regular consumer of GPU compute
    'provider',    -- owns and registers GPU servers
    'admin'        -- platform administrator
);

CREATE TYPE server_status AS ENUM (
    'pending',     -- registered, awaiting admin approval
    'online',      -- heartbeat received within last 90s
    'offline',     -- no heartbeat for 90s
    'busy',        -- all GPU slots occupied
    'maintenance', -- manually taken offline by provider/admin
    'banned'       -- flagged and removed from pool
);

CREATE TYPE job_status AS ENUM (
    'queued',      -- in BullMQ queue, waiting for server
    'dispatched',  -- sent to agent, awaiting confirmation
    'running',     -- agent confirmed, Docker container active
    'completed',   -- exited with code 0
    'failed',      -- exited with non-zero code or timed out
    'cancelled',   -- cancelled by user before completion
    'refunded'     -- failed and tokens were refunded
);

CREATE TYPE ledger_entry_type AS ENUM (
    'purchase',         -- user bought tokens via Stripe
    'job_lock',         -- tokens locked at job submission
    'job_lock_release', -- locked tokens released (over-estimate)
    'job_debit',        -- final actual charge for completed job
    'job_refund',       -- tokens returned on failure
    'admin_credit',     -- manual credit by admin
    'admin_debit',      -- manual debit by admin
    'provider_payout'   -- tokens converted to cash payout
);

CREATE TYPE gpu_framework AS ENUM (
    'pytorch',
    'tensorflow',
    'jax',
    'onnx',
    'cuda_raw',
    'any'
);

CREATE TYPE payout_status AS ENUM (
    'pending',
    'processing',
    'paid',
    'failed'
);


-- =============================================================================
-- CORE TABLES
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. USERS
-- -----------------------------------------------------------------------------
CREATE TABLE users (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email               TEXT NOT NULL,
    hashed_password     TEXT NOT NULL,
    full_name           TEXT,
    role                user_role NOT NULL DEFAULT 'user',

    -- token balance is a DENORMALIZED cache of the ledger sum.
    -- always recompute from token_ledger for billing-critical operations.
    token_balance       BIGINT NOT NULL DEFAULT 0 CHECK (token_balance >= 0),

    -- account state
    is_verified         BOOLEAN NOT NULL DEFAULT FALSE,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    verify_token        TEXT,                         -- email verification token
    reset_token         TEXT,                         -- password reset token
    reset_token_expires TIMESTAMPTZ,

    -- stripe
    stripe_customer_id  TEXT UNIQUE,

    -- metadata
    avatar_url          TEXT,
    timezone            TEXT DEFAULT 'UTC',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at       TIMESTAMPTZ
);

CREATE UNIQUE INDEX users_email_lower_idx ON users (LOWER(email));
CREATE INDEX users_role_idx ON users (role);
CREATE INDEX users_stripe_customer_idx ON users (stripe_customer_id) WHERE stripe_customer_id IS NOT NULL;


-- -----------------------------------------------------------------------------
-- 2. USER SESSIONS (JWT refresh token tracking)
-- -----------------------------------------------------------------------------
CREATE TABLE user_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    refresh_token   TEXT NOT NULL UNIQUE,   -- hashed before storing
    user_agent      TEXT,
    ip_address      INET,
    expires_at      TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at      TIMESTAMPTZ             -- NULL = still valid
);

CREATE INDEX sessions_user_idx ON user_sessions (user_id);
CREATE INDEX sessions_expires_idx ON user_sessions (expires_at);


-- =============================================================================
-- TOKEN / BILLING TABLES
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 3. TOKEN PACKAGES (admin-defined purchase options)
-- -----------------------------------------------------------------------------
CREATE TABLE token_packages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,           -- e.g. "Starter", "Pro", "Enterprise"
    token_amount    BIGINT NOT NULL,         -- tokens granted
    price_inr       NUMERIC(10,2) NOT NULL,  -- price in INR (paise-safe)
    price_usd       NUMERIC(10,2),           -- optional USD price
    bonus_tokens    BIGINT NOT NULL DEFAULT 0, -- extra tokens (promotions)
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order      INT NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO token_packages (name, token_amount, price_inr, sort_order) VALUES
    ('Starter',    500,   199.00, 1),
    ('Developer',  2000,  699.00, 2),
    ('Pro',        6000,  1899.00, 3),
    ('Enterprise', 20000, 5499.00, 4);


-- -----------------------------------------------------------------------------
-- 4. TOKEN LEDGER (immutable double-entry log)
-- -----------------------------------------------------------------------------
-- This is the source of truth for all token movements.
-- NEVER update or delete rows. INSERT ONLY.
CREATE TABLE token_ledger (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    amount          BIGINT NOT NULL,          -- positive = credit, negative = debit
    entry_type      ledger_entry_type NOT NULL,
    balance_after   BIGINT NOT NULL,          -- snapshot of balance after this entry

    -- reference to the object that caused this entry
    ref_job_id      UUID,                     -- FK set below (circular ref avoidance)
    ref_payment_id  UUID,                     -- FK to payments
    ref_package_id  UUID REFERENCES token_packages(id),

    description     TEXT,                     -- human-readable note
    metadata        JSONB DEFAULT '{}',       -- arbitrary extra data

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by      UUID REFERENCES users(id) -- NULL = system, admin UUID = manual
);

CREATE INDEX ledger_user_idx ON token_ledger (user_id, created_at DESC);
CREATE INDEX ledger_job_idx ON token_ledger (ref_job_id) WHERE ref_job_id IS NOT NULL;
CREATE INDEX ledger_type_idx ON token_ledger (entry_type, created_at DESC);


-- -----------------------------------------------------------------------------
-- 5. PAYMENTS (Stripe checkout records)
-- -----------------------------------------------------------------------------
CREATE TABLE payments (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    package_id              UUID REFERENCES token_packages(id),

    -- stripe identifiers
    stripe_payment_intent_id TEXT UNIQUE,
    stripe_checkout_session_id TEXT UNIQUE,
    stripe_invoice_id        TEXT,

    amount_inr              NUMERIC(10,2) NOT NULL,
    tokens_credited         BIGINT NOT NULL,
    status                  TEXT NOT NULL DEFAULT 'pending', -- pending|succeeded|failed|refunded
    payment_method          TEXT,            -- card, upi, netbanking etc.
    receipt_url             TEXT,

    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at            TIMESTAMPTZ
);

CREATE INDEX payments_user_idx ON payments (user_id, created_at DESC);
CREATE INDEX payments_stripe_intent_idx ON payments (stripe_payment_intent_id);


-- =============================================================================
-- GPU SERVER TABLES
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 6. GPU SERVER REGISTRATIONS
-- -----------------------------------------------------------------------------
CREATE TABLE gpu_servers (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id         UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,

    -- identification
    name                TEXT NOT NULL,            -- human name, e.g. "A100 Node 1"
    hostname            TEXT,
    location_country    TEXT NOT NULL DEFAULT 'IN',
    location_region     TEXT,                     -- e.g. "Mumbai", "us-east-1"

    -- GPU specs
    gpu_model           TEXT NOT NULL,            -- e.g. "NVIDIA A100 80GB"
    gpu_count           INT NOT NULL DEFAULT 1 CHECK (gpu_count > 0),
    vram_mb             INT NOT NULL,             -- VRAM per GPU in MB
    total_ram_mb        INT,
    cpu_cores           INT,
    cuda_version        TEXT,                     -- e.g. "12.2"
    driver_version      TEXT,

    -- supported workloads
    supported_frameworks gpu_framework[] NOT NULL DEFAULT ARRAY['any']::gpu_framework[],
    max_concurrent_jobs  INT NOT NULL DEFAULT 1 CHECK (max_concurrent_jobs > 0),

    -- token pricing (tokens per GPU-hour for THIS server)
    tokens_per_gpu_hour  INT NOT NULL,

    -- auth
    api_key_hash        TEXT NOT NULL UNIQUE,     -- SHA-256 of the issued key
    api_key_prefix      TEXT NOT NULL,            -- first 8 chars for display: "gpukey_xxxx..."

    -- status
    status              server_status NOT NULL DEFAULT 'pending',
    last_heartbeat_at   TIMESTAMPTZ,
    approved_at         TIMESTAMPTZ,
    approved_by         UUID REFERENCES users(id),

    -- earnings
    total_gpu_seconds_served BIGINT NOT NULL DEFAULT 0,
    total_tokens_earned      BIGINT NOT NULL DEFAULT 0,

    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX servers_provider_idx ON gpu_servers (provider_id);
CREATE INDEX servers_status_idx ON gpu_servers (status);
CREATE INDEX servers_gpu_model_idx ON gpu_servers (gpu_model);
CREATE INDEX servers_last_heartbeat_idx ON gpu_servers (last_heartbeat_at);


-- -----------------------------------------------------------------------------
-- 7. SERVER HEARTBEATS (time-series, recent readings)
-- -----------------------------------------------------------------------------
-- Keep the last 24h only. Archive to TimescaleDB/S3 if needed.
CREATE TABLE server_heartbeats (
    id              BIGSERIAL PRIMARY KEY,
    server_id       UUID NOT NULL REFERENCES gpu_servers(id) ON DELETE CASCADE,
    cpu_pct         SMALLINT CHECK (cpu_pct BETWEEN 0 AND 100),
    gpu_pct         SMALLINT CHECK (gpu_pct BETWEEN 0 AND 100),
    vram_used_mb    INT,
    vram_free_mb    INT,
    ram_used_mb     INT,
    temp_celsius    SMALLINT,
    jobs_running    SMALLINT NOT NULL DEFAULT 0,
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX heartbeats_server_time_idx ON server_heartbeats (server_id, recorded_at DESC);

-- auto-purge heartbeats older than 24 hours (run via pg_cron or app cron)
-- DELETE FROM server_heartbeats WHERE recorded_at < NOW() - INTERVAL '24 hours';


-- =============================================================================
-- JOB TABLES
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 8. JOBS
-- -----------------------------------------------------------------------------
CREATE TABLE jobs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    server_id           UUID REFERENCES gpu_servers(id) ON DELETE SET NULL,

    -- workload definition
    docker_image        TEXT NOT NULL,            -- e.g. "pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime"
    command             TEXT[],                   -- override CMD, e.g. ["python", "train.py"]
    env_vars            JSONB DEFAULT '{}',       -- {KEY: VALUE} pairs (encrypted at app layer)
    required_gpu_model  TEXT,                     -- NULL = any GPU
    required_vram_mb    INT DEFAULT 0,
    required_framework  gpu_framework DEFAULT 'any',
    max_runtime_minutes INT NOT NULL DEFAULT 60 CHECK (max_runtime_minutes BETWEEN 1 AND 1440),
    gpu_count           INT NOT NULL DEFAULT 1,
    priority            SMALLINT NOT NULL DEFAULT 5 CHECK (priority BETWEEN 1 AND 10),

    -- status tracking
    status              job_status NOT NULL DEFAULT 'queued',
    queue_position      INT,                      -- position in queue when queued
    retry_count         SMALLINT NOT NULL DEFAULT 0,
    max_retries         SMALLINT NOT NULL DEFAULT 2,
    exit_code           INT,
    error_message       TEXT,

    -- billing
    tokens_locked       BIGINT NOT NULL DEFAULT 0,  -- reserved at submission
    tokens_billed       BIGINT,                     -- actual charge (set on completion)
    gpu_seconds_used    INT,                        -- from agent final report
    peak_vram_mb        INT,

    -- timing
    queued_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    dispatched_at       TIMESTAMPTZ,
    started_at          TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,

    -- output
    log_storage_key     TEXT,                       -- S3/R2 key for stored logs
    result_storage_key  TEXT,                       -- S3/R2 key for output artifacts

    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX jobs_user_idx ON jobs (user_id, created_at DESC);
CREATE INDEX jobs_server_idx ON jobs (server_id) WHERE server_id IS NOT NULL;
CREATE INDEX jobs_status_idx ON jobs (status, queued_at);
CREATE INDEX jobs_queued_priority_idx ON jobs (priority DESC, queued_at ASC) WHERE status = 'queued';

-- Add FK from ledger to jobs (after jobs table exists)
ALTER TABLE token_ledger ADD CONSTRAINT fk_ledger_job
    FOREIGN KEY (ref_job_id) REFERENCES jobs(id) ON DELETE SET NULL;


-- -----------------------------------------------------------------------------
-- 9. JOB LOGS (chunked stdout/stderr from agent)
-- -----------------------------------------------------------------------------
CREATE TABLE job_logs (
    id          BIGSERIAL PRIMARY KEY,
    job_id      UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    stream      TEXT NOT NULL DEFAULT 'stdout' CHECK (stream IN ('stdout', 'stderr', 'system')),
    chunk       TEXT NOT NULL,
    seq         INT NOT NULL,               -- ordering sequence from agent
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX job_logs_job_seq_idx ON job_logs (job_id, seq ASC);


-- -----------------------------------------------------------------------------
-- 10. JOB USAGE SAMPLES (per-job GPU metrics from nvidia-smi)
-- -----------------------------------------------------------------------------
CREATE TABLE job_usage_samples (
    id              BIGSERIAL PRIMARY KEY,
    job_id          UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    gpu_pct         SMALLINT,
    vram_used_mb    INT,
    power_watts     SMALLINT,
    temp_celsius    SMALLINT,
    sampled_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX usage_samples_job_idx ON job_usage_samples (job_id, sampled_at DESC);


-- =============================================================================
-- PROVIDER EARNINGS & PAYOUTS
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 11. PROVIDER EARNINGS LEDGER
-- -----------------------------------------------------------------------------
CREATE TABLE provider_earnings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id     UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    server_id       UUID REFERENCES gpu_servers(id) ON DELETE SET NULL,
    job_id          UUID REFERENCES jobs(id) ON DELETE SET NULL,

    tokens_earned   BIGINT NOT NULL,              -- tokens earned for this job
    gpu_seconds     INT NOT NULL,
    platform_fee_pct NUMERIC(5,2) NOT NULL DEFAULT 20.00, -- platform takes 20%
    tokens_after_fee BIGINT NOT NULL,             -- tokens_earned * (1 - fee%)

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX provider_earnings_provider_idx ON provider_earnings (provider_id, created_at DESC);
CREATE INDEX provider_earnings_server_idx ON provider_earnings (server_id);


-- -----------------------------------------------------------------------------
-- 12. PAYOUTS (provider cash withdrawals)
-- -----------------------------------------------------------------------------
CREATE TABLE provider_payouts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id         UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    tokens_redeemed     BIGINT NOT NULL,
    amount_inr          NUMERIC(10,2) NOT NULL,
    bank_account_last4  TEXT,
    upi_id              TEXT,
    status              payout_status NOT NULL DEFAULT 'pending',
    razorpay_payout_id  TEXT UNIQUE,
    notes               TEXT,
    initiated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at        TIMESTAMPTZ
);

CREATE INDEX payouts_provider_idx ON provider_payouts (provider_id, initiated_at DESC);


-- =============================================================================
-- GPU PRICING TABLE
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 13. GPU TIER PRICING (admin-controlled per GPU model)
-- -----------------------------------------------------------------------------
CREATE TABLE gpu_pricing (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    gpu_model_pattern   TEXT NOT NULL UNIQUE,   -- e.g. "NVIDIA A100%" (LIKE pattern)
    display_name        TEXT NOT NULL,           -- e.g. "A100 80GB"
    tokens_per_gpu_hour INT NOT NULL,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by          UUID REFERENCES users(id)
);

INSERT INTO gpu_pricing (gpu_model_pattern, display_name, tokens_per_gpu_hour) VALUES
    ('NVIDIA A100%',      'A100',      100),
    ('NVIDIA H100%',      'H100',      180),
    ('NVIDIA RTX 4090%',  'RTX 4090',  40),
    ('NVIDIA RTX 3090%',  'RTX 3090',  25),
    ('NVIDIA T4%',        'T4',        15),
    ('NVIDIA V100%',      'V100',      60);


-- =============================================================================
-- PLATFORM ADMIN TABLES
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 14. AUDIT LOG (admin actions trail)
-- -----------------------------------------------------------------------------
CREATE TABLE audit_log (
    id          BIGSERIAL PRIMARY KEY,
    actor_id    UUID REFERENCES users(id) ON DELETE SET NULL,
    action      TEXT NOT NULL,               -- e.g. "approve_server", "ban_user", "manual_credit"
    target_type TEXT,                        -- e.g. "user", "server", "job"
    target_id   TEXT,                        -- UUID as text (flexible)
    old_value   JSONB,
    new_value   JSONB,
    ip_address  INET,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX audit_log_actor_idx ON audit_log (actor_id, created_at DESC);
CREATE INDEX audit_log_target_idx ON audit_log (target_type, target_id);


-- -----------------------------------------------------------------------------
-- 15. PLATFORM SETTINGS (key-value config store)
-- -----------------------------------------------------------------------------
CREATE TABLE platform_settings (
    key         TEXT PRIMARY KEY,
    value       JSONB NOT NULL,
    description TEXT,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by  UUID REFERENCES users(id)
);

INSERT INTO platform_settings (key, value, description) VALUES
    ('platform_fee_pct',        '20',                          'Platform commission % on provider earnings'),
    ('min_token_lock_buffer',   '1.2',                         'Multiplier for token lock (20% over-reserve)'),
    ('heartbeat_timeout_secs',  '90',                          'Seconds before server marked offline'),
    ('max_job_retries',         '2',                           'Default max retries on job failure'),
    ('payout_hold_days',        '7',                           'Days to hold provider payouts'),
    ('token_to_inr_rate',       '0.05',                        'INR value per token for payout conversion'),
    ('maintenance_mode',        'false',                       'Halt all new job submissions');


-- =============================================================================
-- FUNCTIONS & TRIGGERS
-- =============================================================================


-- -----------------------------------------------------------------------------
-- updated_at auto-update trigger
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER users_updated_at         BEFORE UPDATE ON users         FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER servers_updated_at       BEFORE UPDATE ON gpu_servers   FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER jobs_updated_at          BEFORE UPDATE ON jobs          FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- -----------------------------------------------------------------------------
-- Sync users.token_balance from ledger on every ledger INSERT
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION sync_user_token_balance()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE users
    SET token_balance = NEW.balance_after
    WHERE id = NEW.user_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER ledger_sync_balance
    AFTER INSERT ON token_ledger
    FOR EACH ROW EXECUTE FUNCTION sync_user_token_balance();


-- -----------------------------------------------------------------------------
-- Auto-mark server online/offline based on heartbeat age
-- (call this via a cron job every 30s, or from your scheduler worker)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION refresh_server_statuses()
RETURNS void AS $$
BEGIN
    -- mark online servers as offline if heartbeat is stale
    UPDATE gpu_servers
    SET status = 'offline', updated_at = NOW()
    WHERE status = 'online'
      AND last_heartbeat_at < NOW() - INTERVAL '90 seconds';

    -- mark offline servers as online if fresh heartbeat received
    UPDATE gpu_servers
    SET status = 'online', updated_at = NOW()
    WHERE status = 'offline'
      AND last_heartbeat_at >= NOW() - INTERVAL '90 seconds'
      AND approved_at IS NOT NULL;
END;
$$ LANGUAGE plpgsql;


-- -----------------------------------------------------------------------------
-- Helper: get current token balance (authoritative, reads ledger)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION get_user_balance(p_user_id UUID)
RETURNS BIGINT AS $$
    SELECT COALESCE(SUM(amount), 0)
    FROM token_ledger
    WHERE user_id = p_user_id;
$$ LANGUAGE sql STABLE;


-- -----------------------------------------------------------------------------
-- Helper: calculate token cost for a job
-- usage: SELECT calculate_job_tokens('server-uuid', 3600);
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION calculate_job_tokens(
    p_server_id UUID,
    p_gpu_seconds INT
)
RETURNS BIGINT AS $$
DECLARE
    v_tokens_per_hour INT;
BEGIN
    SELECT tokens_per_gpu_hour INTO v_tokens_per_hour
    FROM gpu_servers WHERE id = p_server_id;

    IF v_tokens_per_hour IS NULL THEN
        RAISE EXCEPTION 'Server not found: %', p_server_id;
    END IF;

    RETURN CEIL((p_gpu_seconds::NUMERIC / 3600) * v_tokens_per_hour);
END;
$$ LANGUAGE plpgsql STABLE;


-- =============================================================================
-- VIEWS
-- =============================================================================


-- -----------------------------------------------------------------------------
-- Live server pool (only schedulable servers)
-- -----------------------------------------------------------------------------
CREATE VIEW available_servers AS
SELECT
    s.id,
    s.name,
    s.gpu_model,
    s.gpu_count,
    s.vram_mb,
    s.tokens_per_gpu_hour,
    s.location_country,
    s.location_region,
    s.supported_frameworks,
    s.max_concurrent_jobs,
    s.last_heartbeat_at,
    COALESCE(
        (SELECT COUNT(*) FROM jobs j
         WHERE j.server_id = s.id AND j.status IN ('dispatched','running')),
        0
    ) AS active_jobs,
    s.max_concurrent_jobs - COALESCE(
        (SELECT COUNT(*) FROM jobs j
         WHERE j.server_id = s.id AND j.status IN ('dispatched','running')),
        0
    ) AS free_slots
FROM gpu_servers s
WHERE s.status = 'online'
  AND s.approved_at IS NOT NULL;


-- -----------------------------------------------------------------------------
-- User dashboard summary
-- -----------------------------------------------------------------------------
CREATE VIEW user_dashboard AS
SELECT
    u.id,
    u.email,
    u.full_name,
    u.token_balance,
    COUNT(j.id) FILTER (WHERE j.status = 'running')    AS jobs_running,
    COUNT(j.id) FILTER (WHERE j.status = 'queued')     AS jobs_queued,
    COUNT(j.id) FILTER (WHERE j.status = 'completed')  AS jobs_completed,
    COUNT(j.id) FILTER (WHERE j.status = 'failed')     AS jobs_failed,
    COALESCE(SUM(j.tokens_billed) FILTER (WHERE j.status = 'completed'), 0) AS lifetime_tokens_spent,
    COALESCE(SUM(j.gpu_seconds_used) FILTER (WHERE j.status = 'completed'), 0) AS lifetime_gpu_seconds
FROM users u
LEFT JOIN jobs j ON j.user_id = u.id
GROUP BY u.id;


-- -----------------------------------------------------------------------------
-- Provider earnings summary
-- -----------------------------------------------------------------------------
CREATE VIEW provider_summary AS
SELECT
    u.id AS provider_id,
    u.email,
    u.full_name,
    COUNT(s.id) AS server_count,
    COUNT(s.id) FILTER (WHERE s.status = 'online') AS servers_online,
    COALESCE(SUM(pe.tokens_after_fee), 0) AS total_tokens_earned,
    COALESCE(SUM(pp.tokens_redeemed), 0)  AS total_tokens_paid_out,
    COALESCE(SUM(pe.tokens_after_fee), 0) -
    COALESCE(SUM(pp.tokens_redeemed), 0)  AS tokens_available_to_withdraw
FROM users u
LEFT JOIN gpu_servers s     ON s.provider_id = u.id
LEFT JOIN provider_earnings pe ON pe.provider_id = u.id
LEFT JOIN provider_payouts pp  ON pp.provider_id = u.id AND pp.status = 'paid'
WHERE u.role = 'provider'
GROUP BY u.id;


-- =============================================================================
-- ROW LEVEL SECURITY (enable for Supabase or direct PostgREST usage)
-- =============================================================================

-- ALTER TABLE users           ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE token_ledger    ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE jobs            ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE gpu_servers     ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE job_logs        ENABLE ROW LEVEL SECURITY;

-- Example RLS policies (uncomment if using Supabase/PostgREST):
-- CREATE POLICY "Users see own row"    ON users        FOR SELECT USING (auth.uid() = id);
-- CREATE POLICY "Users see own ledger" ON token_ledger FOR SELECT USING (auth.uid() = user_id);
-- CREATE POLICY "Users see own jobs"   ON jobs         FOR SELECT USING (auth.uid() = user_id);


-- =============================================================================
-- END OF SCHEMA
-- =============================================================================
