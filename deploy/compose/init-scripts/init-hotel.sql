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
-- Indexes for better query performance
-- =============================================================================
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
