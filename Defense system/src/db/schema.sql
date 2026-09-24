CREATE TABLE IF NOT EXISTS flagged_transactions (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    txn_id            VARCHAR(64) UNIQUE NOT NULL,
    phone_number      VARCHAR(20) NOT NULL,
    amount            DECIMAL(15,2) NOT NULL,
    fraud_score       DECIMAL(6,5) NOT NULL,
    risk_level        VARCHAR(10) NOT NULL,
    in_flagged_ring   BOOLEAN DEFAULT FALSE,
    top_reasons       JSON,           -- SHAP top-3 contributions
    features_json     JSON,           -- exact feature vector at scoring time
    status            VARCHAR(30) NOT NULL DEFAULT 'scored',
    resolution_method VARCHAR(60),
    resolution_note   TEXT,
    scored_at         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at        TIMESTAMP NULL
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS flagged_clusters (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    sender_count INT NOT NULL,
    flagged_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS ring_edges (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    cluster_id   INT,
    sender_id    VARCHAR(64) NOT NULL,
    device_id    VARCHAR(64) NOT NULL,
    dest_account VARCHAR(64) NOT NULL,
    FOREIGN KEY (cluster_id) REFERENCES flagged_clusters(id) ON DELETE CASCADE
) ENGINE=InnoDB;-- Logs freeze requests rather than calling a real core-banking freeze-- API directly - that integration is telecom/partner-specific.
CREATE TABLE IF NOT EXISTS account_actions (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    phone_number VARCHAR(20) NOT NULL,
    action       VARCHAR(30) NOT NULL,
    txn_id       VARCHAR(64),
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;