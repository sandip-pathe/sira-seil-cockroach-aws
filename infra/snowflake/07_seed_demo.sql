-- 07_seed_demo.sql — Seed fictional meeting-intelligence scenario
-- Run as ACCOUNTADMIN after all tables exist; this seed also grants staged objects.

USE ROLE ACCOUNTADMIN;
USE WAREHOUSE SIRA_HACK_XS_WH;

-- ============================================================
-- COMPANY
-- ============================================================
USE SCHEMA SIRA_HACKATHON.GOVERNED;

INSERT INTO COMPANIES (company_id, name)
  SELECT 'comp_consultco', 'ConsultCo'
  WHERE NOT EXISTS (SELECT 1 FROM COMPANIES WHERE company_id = 'comp_consultco');

-- ============================================================
-- PRODUCTS (meeting intelligence tools)
-- ============================================================
INSERT INTO PRODUCTS (product_id, seller_id, name, category, product_version, status)
  SELECT column1, column2, column3, column4, column5, column6
  FROM VALUES
    ('prod_meetai_a', 'seller_meetai', 'MeetAI Pro', 'meeting_intelligence', 1, 'ACTIVE'),
    ('prod_notesync_b', 'seller_notesync', 'NoteSync Teams', 'meeting_intelligence', 1, 'ACTIVE')
  WHERE NOT EXISTS (SELECT 1 FROM PRODUCTS WHERE product_id = 'prod_meetai_a');

-- ============================================================
-- OFFERS
-- Product A: $80/seat/month standard, $120/seat/month with HubSpot
-- Product B: $95/seat/month includes HubSpot natively
-- ============================================================
INSERT INTO OFFERS (offer_id, product_id, tier, unit_price, billing_unit, currency, min_seats, max_seats)
  SELECT column1, column2, column3, column4, column5, column6, column7, column8
  FROM VALUES
    ('offer_meetai_standard', 'prod_meetai_a', 'Standard', 80.00, 'seat/month', 'USD', 1, 100),
    ('offer_meetai_hubspot', 'prod_meetai_a', 'HubSpot Integration', 120.00, 'seat/month', 'USD', 1, 100),
    ('offer_notesync_team', 'prod_notesync_b', 'Team', 95.00, 'seat/month', 'USD', 1, 50)
  WHERE NOT EXISTS (SELECT 1 FROM OFFERS WHERE offer_id = 'offer_meetai_standard');

-- ============================================================
-- BUYER CONTEXT VERSION 1: HubSpot is mandatory (CRM_SYNC_REQUIRED=true)
-- 10 seats, $100/seat/month budget, HubSpot required
-- ============================================================
INSERT INTO COMPANY_FACTS (fact_id, company_id, context_version, fact_key, typed_value, visibility, source_kind, source_ref, valid_from)
  SELECT column1, column2, column3, column4, PARSE_JSON(column5), column6, column7, column8, column9::TIMESTAMP_NTZ
  FROM VALUES
    ('fact_v1_seats', 'comp_consultco', 1, 'REQUIRED_SEATS', '10', 'PRIVATE', 'ADMIN_INPUT', 'purchase_brief_v1', '2026-08-01 00:00:00'),
    ('fact_v1_budget', 'comp_consultco', 1, 'MAX_UNIT_PRICE', '100.00', 'PRIVATE', 'ADMIN_INPUT', 'budget_approval_v1', '2026-08-01 00:00:00'),
    ('fact_v1_crm_required', 'comp_consultco', 1, 'CRM_SYNC_REQUIRED', 'true', 'PRIVATE', 'ADMIN_INPUT', 'ops_requirement_v1', '2026-08-01 00:00:00'),
    ('fact_v1_crm_name', 'comp_consultco', 1, 'CURRENT_CRM', '"HubSpot"', 'PRIVATE', 'STACKFILE', 'stackfile_lock_v1', '2026-08-01 00:00:00'),
    ('fact_v1_category', 'comp_consultco', 1, 'CATEGORY', '"meeting_intelligence"', 'INTERNAL', 'ADMIN_INPUT', 'purchase_brief_v1', '2026-08-01 00:00:00')
  WHERE NOT EXISTS (SELECT 1 FROM COMPANY_FACTS WHERE fact_id = 'fact_v1_seats');

-- ============================================================
-- BUYER CONTEXT VERSION 2: HubSpot NOT required (CRM_SYNC_REQUIRED absent)
-- Same seats, same budget, but no CRM sync requirement
-- ============================================================
INSERT INTO COMPANY_FACTS (fact_id, company_id, context_version, fact_key, typed_value, visibility, source_kind, source_ref, valid_from)
  SELECT column1, column2, column3, column4, PARSE_JSON(column5), column6, column7, column8, column9::TIMESTAMP_NTZ
  FROM VALUES
    ('fact_v2_seats', 'comp_consultco', 2, 'REQUIRED_SEATS', '10', 'PRIVATE', 'ADMIN_INPUT', 'purchase_brief_v2', '2026-08-01 00:00:00'),
    ('fact_v2_budget', 'comp_consultco', 2, 'MAX_UNIT_PRICE', '100.00', 'PRIVATE', 'ADMIN_INPUT', 'budget_approval_v2', '2026-08-01 00:00:00'),
    ('fact_v2_category', 'comp_consultco', 2, 'CATEGORY', '"meeting_intelligence"', 'INTERNAL', 'ADMIN_INPUT', 'purchase_brief_v2', '2026-08-01 00:00:00')
  WHERE NOT EXISTS (SELECT 1 FROM COMPANY_FACTS WHERE fact_id = 'fact_v2_seats');

-- Version 2 does NOT have CRM_SYNC_REQUIRED or CURRENT_CRM facts.
-- This is the decisive difference: without CRM requirement, Product A's
-- $80 Standard tier wins on price alone.
