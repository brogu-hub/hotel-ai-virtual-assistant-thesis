-- =============================================================================
-- Hotel AI Operations Assistant - Database Schema
-- =============================================================================

-- =============================================================================
-- Room Types Table
-- =============================================================================
CREATE TABLE IF NOT EXISTS room_types (
    room_type_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    name_th VARCHAR(100),
    description TEXT,
    description_th TEXT,
    base_price DECIMAL(10, 2) NOT NULL,
    max_occupancy INTEGER NOT NULL,
    amenities JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- Rooms Table
-- =============================================================================
CREATE TABLE IF NOT EXISTS rooms (
    room_id SERIAL PRIMARY KEY,
    room_number VARCHAR(20) UNIQUE NOT NULL,
    room_type_id INTEGER REFERENCES room_types(room_type_id),
    floor INTEGER,
    status VARCHAR(50) DEFAULT 'available',
    view_type VARCHAR(50),
    last_cleaned TIMESTAMP,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- Guests Table
-- =============================================================================
CREATE TABLE IF NOT EXISTS guests (
    guest_id SERIAL PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    first_name_th VARCHAR(100),
    last_name_th VARCHAR(100),
    email VARCHAR(255) UNIQUE,
    phone VARCHAR(50),
    id_number VARCHAR(50),
    nationality VARCHAR(50),
    loyalty_tier VARCHAR(50) DEFAULT 'Standard',
    loyalty_points INTEGER DEFAULT 0,
    preferences JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- Reservations Table
-- =============================================================================
CREATE TABLE IF NOT EXISTS reservations (
    reservation_id SERIAL PRIMARY KEY,
    confirmation_number VARCHAR(20) UNIQUE,
    guest_id INTEGER REFERENCES guests(guest_id),
    room_id INTEGER REFERENCES rooms(room_id),
    check_in_date DATE NOT NULL,
    check_out_date DATE NOT NULL,
    num_guests INTEGER DEFAULT 1,
    status VARCHAR(50) DEFAULT 'pending',
    total_amount DECIMAL(10, 2),
    payment_status VARCHAR(50) DEFAULT 'pending',
    special_requests TEXT,
    booking_source VARCHAR(100),
    cancellation_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- Service Requests Table
-- =============================================================================
CREATE TABLE IF NOT EXISTS service_requests (
    request_id SERIAL PRIMARY KEY,
    reservation_id INTEGER REFERENCES reservations(reservation_id),
    guest_id INTEGER REFERENCES guests(guest_id),
    request_type VARCHAR(100) NOT NULL,
    description TEXT,
    description_th TEXT,
    status VARCHAR(50) DEFAULT 'pending',
    priority VARCHAR(20) DEFAULT 'normal',
    assigned_to VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP
);

-- =============================================================================
-- Housekeeping Schedule Table
-- =============================================================================
CREATE TABLE IF NOT EXISTS housekeeping (
    task_id SERIAL PRIMARY KEY,
    room_id INTEGER REFERENCES rooms(room_id),
    task_type VARCHAR(100) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    assigned_to VARCHAR(100),
    scheduled_date DATE,
    completed_at TIMESTAMP,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- Hotel Services/Amenities Table
-- =============================================================================
CREATE TABLE IF NOT EXISTS hotel_services (
    service_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    name_th VARCHAR(100),
    category VARCHAR(100),
    description TEXT,
    description_th TEXT,
    price DECIMAL(10, 2),
    availability_hours VARCHAR(100),
    location VARCHAR(100),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- Conversation History Table (for AI context)
-- =============================================================================
CREATE TABLE IF NOT EXISTS conversation_history (
    conversation_id SERIAL PRIMARY KEY,
    session_id VARCHAR(100) NOT NULL,
    guest_id INTEGER REFERENCES guests(guest_id),
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- Users Table (authentication: registered guests + admins)
-- =============================================================================
CREATE TABLE IF NOT EXISTS users (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(64) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'user',
    full_name VARCHAR(200),
    is_active BOOLEAN DEFAULT TRUE,
    guest_id INTEGER REFERENCES guests(guest_id) ON DELETE SET NULL,
    last_login TIMESTAMP,
    failed_login_attempts INTEGER DEFAULT 0,
    locked_until TIMESTAMP,
    password_changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    password_is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT users_role_check CHECK (role IN ('user', 'admin'))
);

-- =============================================================================
-- Audit Log Table (admin actions + auth events + privacy-sensitive ops)
-- =============================================================================
CREATE TABLE IF NOT EXISTS audit_log (
    audit_id BIGSERIAL PRIMARY KEY,
    actor_user_id INTEGER REFERENCES users(user_id) ON DELETE SET NULL,
    actor_username VARCHAR(64),
    actor_role VARCHAR(20),
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50),
    resource_id VARCHAR(100),
    details JSONB,
    ip_address VARCHAR(45),
    user_agent VARCHAR(500),
    success BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- Indexes for better query performance
-- =============================================================================
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_audit_log_actor ON audit_log(actor_user_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_created ON audit_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_log_resource ON audit_log(resource_type, resource_id);
CREATE INDEX IF NOT EXISTS idx_conversation_created ON conversation_history(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_conversation_session_created ON conversation_history(session_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_reservations_guest ON reservations(guest_id);
CREATE INDEX IF NOT EXISTS idx_reservations_dates ON reservations(check_in_date, check_out_date);
CREATE INDEX IF NOT EXISTS idx_reservations_status ON reservations(status);
CREATE INDEX IF NOT EXISTS idx_reservations_confirmation ON reservations(confirmation_number);
CREATE INDEX IF NOT EXISTS idx_service_requests_status ON service_requests(status);
CREATE INDEX IF NOT EXISTS idx_housekeeping_status ON housekeeping(status);
CREATE INDEX IF NOT EXISTS idx_rooms_status ON rooms(status);
CREATE INDEX IF NOT EXISTS idx_guests_email ON guests(email);
CREATE INDEX IF NOT EXISTS idx_conversation_session ON conversation_history(session_id);

-- =============================================================================
-- Function to generate confirmation number
-- =============================================================================
CREATE OR REPLACE FUNCTION generate_confirmation_number()
RETURNS TRIGGER AS $$
BEGIN
    NEW.confirmation_number := 'HTL' || TO_CHAR(NOW(), 'YYMMDD') || LPAD(NEW.reservation_id::TEXT, 4, '0');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for confirmation number
DROP TRIGGER IF EXISTS set_confirmation_number ON reservations;
CREATE TRIGGER set_confirmation_number
    BEFORE INSERT ON reservations
    FOR EACH ROW
    WHEN (NEW.confirmation_number IS NULL)
    EXECUTE FUNCTION generate_confirmation_number();

-- =============================================================================
-- Function to update timestamp
-- =============================================================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create triggers for updated_at
DROP TRIGGER IF EXISTS update_reservations_updated_at ON reservations;
CREATE TRIGGER update_reservations_updated_at
    BEFORE UPDATE ON reservations
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

DROP TRIGGER IF EXISTS update_guests_updated_at ON guests;
CREATE TRIGGER update_guests_updated_at
    BEFORE UPDATE ON guests
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- =============================================================================
-- Application Role: hotel_app (least-privilege)
-- =============================================================================
-- Created so the running FastAPI application does NOT connect as the postgres
-- superuser. hotel_app gets exactly the permissions the chat path needs and
-- nothing more. Migrations and admin scripts continue to use postgres.
--
-- Permissions:
--   * SELECT/INSERT/UPDATE on all app tables (room_types, rooms, guests,
--     reservations, service_requests, housekeeping, hotel_services,
--     conversation_history, payment_links).
--   * SELECT/INSERT/UPDATE on users + audit_log (auth + audit need to
--     insert rows; updates needed for last_login, failed_login_attempts).
--   * No DELETE on reservations / audit_log / payment_links — destructive
--     intent must go through soft-delete (status='cancelled') instead.
--   * No DELETE on users either — deactivation goes via is_active=false.
--   * DELETE on housekeeping + service_requests + conversation_history
--     allowed (operational cleanup is normal there).
--   * No DROP / TRUNCATE / ALTER / CREATE permissions on anything.
--   * USAGE on SEQUENCEs (needed for SERIAL columns).
--   * EXECUTE on the two trigger functions (auto-confirmation + updated_at).
--
-- LangGraph framework tables (checkpoints*, store*) are created at runtime
-- by AsyncPostgresSaver.setup() / AsyncPostgresStore.setup() which run
-- under the postgres superuser during the FastAPI lifespan. After they
-- exist, hotel_app needs full DML (incl. DELETE for the 30-day anon
-- TTL sweeper). They get a separate grant block lower down.
-- =============================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'hotel_app') THEN
        CREATE ROLE hotel_app LOGIN PASSWORD 'hotel_app_pass_CHANGE_ME';
    END IF;
END $$;

GRANT CONNECT ON DATABASE hotel TO hotel_app;
GRANT USAGE ON SCHEMA public TO hotel_app;

-- App tables: full read + write, no destructive DDL
GRANT SELECT, INSERT, UPDATE ON
    room_types, rooms, guests, reservations,
    service_requests, housekeeping, hotel_services,
    conversation_history, payment_links,
    users, audit_log
    TO hotel_app;

-- Operational cleanup allowed only on these (normal lifecycle):
GRANT DELETE ON housekeeping, service_requests, conversation_history TO hotel_app;

-- Sequences (needed for SERIAL inserts)
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO hotel_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO hotel_app;

-- Trigger functions defined above
GRANT EXECUTE ON FUNCTION generate_confirmation_number() TO hotel_app;
GRANT EXECUTE ON FUNCTION update_updated_at() TO hotel_app;

-- LangGraph framework tables — granted IF they exist already (otherwise
-- granted at first-run via a separate DO block after lifespan setup()).
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'checkpoints') THEN
        EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON checkpoints, checkpoint_blobs, checkpoint_writes, checkpoint_migrations TO hotel_app';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'store') THEN
        EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON store, store_migrations TO hotel_app';
    END IF;
END $$;

-- Default privileges for any future tables created by postgres in this schema
-- DO NOT give DELETE by default — that has to be granted explicitly per-table.
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE ON TABLES TO hotel_app;
