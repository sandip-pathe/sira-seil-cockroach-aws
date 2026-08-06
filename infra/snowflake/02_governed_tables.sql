-- 02_governed_tables.sql — Governed structured data for buyer/catalog facts
-- Run as SIRA_SF_BUILD_ROLE after 01_bootstrap.sql

USE ROLE SIRA_SF_BUILD_ROLE;
USE WAREHOUSE SIRA_HACK_XS_WH;
USE SCHEMA SIRA_HACKATHON.GOVERNED;

-- ============================================================
-- COMPANIES
-- ============================================================
CREATE TABLE IF NOT EXISTS COMPANIES (
    company_id   VARCHAR(64)   NOT NULL PRIMARY KEY,
    name         VARCHAR(256)  NOT NULL,
    created_at   TIMESTAMP_NTZ NOT NULL DEFAULT CURRENT_TIMESTAMP()
);

-- ============================================================
-- COMPANY_FACTS — versioned private buyer facts
-- ============================================================
CREATE TABLE IF NOT EXISTS COMPANY_FACTS (
    fact_id          VARCHAR(64)   NOT NULL PRIMARY KEY,
    company_id       VARCHAR(64)   NOT NULL REFERENCES COMPANIES(company_id),
    context_version  INTEGER       NOT NULL,
    fact_key         VARCHAR(128)  NOT NULL,
    typed_value      VARIANT       NOT NULL,
    visibility       VARCHAR(32)   NOT NULL DEFAULT 'PRIVATE',
    source_kind      VARCHAR(64)   NOT NULL,
    source_ref       VARCHAR(256),
    valid_from       TIMESTAMP_NTZ NOT NULL,
    inserted_at      TIMESTAMP_NTZ NOT NULL DEFAULT CURRENT_TIMESTAMP()
);

-- ============================================================
-- STACKFILE_FACTS — product-in-stack status
-- ============================================================
CREATE TABLE IF NOT EXISTS STACKFILE_FACTS (
    stack_fact_id    VARCHAR(64)   NOT NULL PRIMARY KEY,
    company_id       VARCHAR(64)   NOT NULL REFERENCES COMPANIES(company_id),
    context_version  INTEGER       NOT NULL,
    product_key      VARCHAR(128)  NOT NULL,
    status           VARCHAR(32)   NOT NULL,
    source_ref       VARCHAR(256),
    inserted_at      TIMESTAMP_NTZ NOT NULL DEFAULT CURRENT_TIMESTAMP()
);

-- ============================================================
-- PRODUCTS
-- ============================================================
CREATE TABLE IF NOT EXISTS PRODUCTS (
    product_id       VARCHAR(64)   NOT NULL PRIMARY KEY,
    seller_id        VARCHAR(64)   NOT NULL,
    name             VARCHAR(256)  NOT NULL,
    category         VARCHAR(128)  NOT NULL,
    product_version  INTEGER       NOT NULL DEFAULT 1,
    status           VARCHAR(32)   NOT NULL DEFAULT 'ACTIVE'
);

-- ============================================================
-- OFFERS
-- ============================================================
CREATE TABLE IF NOT EXISTS OFFERS (
    offer_id         VARCHAR(64)   NOT NULL PRIMARY KEY,
    product_id       VARCHAR(64)   NOT NULL REFERENCES PRODUCTS(product_id),
    tier             VARCHAR(64)   NOT NULL,
    unit_price       NUMBER(12,2)  NOT NULL,
    billing_unit     VARCHAR(32)   NOT NULL DEFAULT 'seat/month',
    currency         VARCHAR(3)    NOT NULL DEFAULT 'USD',
    min_seats        INTEGER       NOT NULL DEFAULT 1,
    max_seats        INTEGER       NOT NULL DEFAULT 1000,
    effective_at     TIMESTAMP_NTZ NOT NULL DEFAULT CURRENT_TIMESTAMP()
);

-- ============================================================
-- V_CURRENT_BUYER_CONTEXT — version-resolved facts for a company+version
-- ============================================================
CREATE OR REPLACE VIEW V_CURRENT_BUYER_CONTEXT AS
SELECT
    cf.fact_id,
    cf.company_id,
    cf.context_version,
    cf.fact_key,
    cf.typed_value,
    cf.visibility,
    cf.source_kind,
    cf.source_ref,
    cf.valid_from
FROM COMPANY_FACTS cf
WHERE cf.visibility IN ('PRIVATE', 'INTERNAL');
