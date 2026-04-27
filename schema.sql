-- Clinic Inventory Management System Database Schema
CREATE DATABASE IF NOT EXISTS clinic_inventory;
USE clinic_inventory;

-- Users table
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    phone VARCHAR(20),
    user_type ENUM('admin','pharmacist','staff') NOT NULL
);

-- Suppliers table
CREATE TABLE suppliers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    company_name VARCHAR(100) NOT NULL,
    email VARCHAR(100),
    phone VARCHAR(20)
);

-- Medicines table
CREATE TABLE medicines (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    quantity INT NOT NULL,
    expiry_date DATE NOT NULL,
    batch_number VARCHAR(50) NOT NULL,
    supplier_id INT,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
);

-- Dispensed medicines table
CREATE TABLE dispensed_medicines (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    batch_number VARCHAR(50) NOT NULL,
    dispensed_by VARCHAR(50) NOT NULL,
    quantity INT NOT NULL,
    dispense_date DATE NOT NULL
);

-- Medicine notifications table
CREATE TABLE medicine_notifications (
    id INT AUTO_INCREMENT PRIMARY KEY,
    medicine_id INT NOT NULL,
    supplier_id INT NOT NULL,
    notified_at DATETIME NOT NULL,
    status ENUM('pending','resolved') DEFAULT 'pending',
    restocked_at DATETIME,
    FOREIGN KEY (medicine_id) REFERENCES medicines(id),
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
);

-- Admin audit log table
CREATE TABLE admin_audit_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    admin_user VARCHAR(50) NOT NULL,
    action VARCHAR(100) NOT NULL,
    resource VARCHAR(100) NOT NULL,
    details TEXT,
    status ENUM('success','failure') NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);
