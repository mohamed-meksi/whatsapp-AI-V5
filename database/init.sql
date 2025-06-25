-- Create the sessions table
CREATE TABLE IF NOT EXISTS sessions (
    id SERIAL PRIMARY KEY,
    location_name VARCHAR(100) NOT NULL,
    address VARCHAR(255) NOT NULL,
    start_date DATE NOT NULL,
    duration VARCHAR(50) NOT NULL,
    schedule VARCHAR(100) NOT NULL,
    spots_available INTEGER NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create the curriculum table
CREATE TABLE IF NOT EXISTS curriculum_items (
    id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES sessions(id),
    technology VARCHAR(100) NOT NULL
);

-- Create the registrations table
CREATE TABLE IF NOT EXISTS registrations (
    id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES sessions(id),
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    phone VARCHAR(50) NOT NULL,
    age INTEGER NOT NULL,
    registration_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) DEFAULT 'pending'
);

-- Insert sample session data
INSERT INTO sessions (location_name, address, start_date, duration, schedule, spots_available, price) VALUES
(
    'Casablanca Ain Chock',
    'Faculté des Sciences Ain Chock, Route d''El Jadida, Casablanca',
    '2024-05-01',
    '12 weeks',
    'Monday-Friday, 9:00 AM - 5:00 PM',
    20,
    8999.00
),
(
    'Casablanca Technopark',
    'Technopark, Route de Nouaceur, Casablanca',
    '2024-06-01',
    '12 weeks',
    'Monday-Friday, 9:00 AM - 5:00 PM',
    15,
    8999.00
),
(
    'Mohammedia',
    'École Nationale Supérieure d''Électricité et de Mécanique, Mohammedia',
    '2024-09-01',
    '12 weeks',
    'Monday-Friday, 9:00 AM - 5:00 PM',
    25,
    8499.00
);

-- Insert curriculum items for each session
INSERT INTO curriculum_items (session_id, technology) 
SELECT 1, technology FROM unnest(ARRAY[
    'HTML/CSS/JavaScript',
    'React',
    'Node.js',
    'Express',
    'MongoDB',
    'Python',
    'Django'
]) AS technology;

INSERT INTO curriculum_items (session_id, technology) 
SELECT 2, technology FROM unnest(ARRAY[
    'HTML/CSS/JavaScript',
    'React',
    'Node.js',
    'Express',
    'MongoDB',
    'Python',
    'Django'
]) AS technology;

INSERT INTO curriculum_items (session_id, technology) 
SELECT 3, technology FROM unnest(ARRAY[
    'HTML/CSS/JavaScript',
    'React',
    'Node.js',
    'Express',
    'MongoDB',
    'Python',
    'Django'
]) AS technology; 