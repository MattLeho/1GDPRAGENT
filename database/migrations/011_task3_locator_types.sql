-- Additive Task 3A provenance vocabulary. Kept separate because PostgreSQL
-- requires newly-added enum values to be committed before they are used.
ALTER TYPE evidence_locator_type ADD VALUE IF NOT EXISTS 'json_record';
ALTER TYPE evidence_locator_type ADD VALUE IF NOT EXISTS 'text_line';
ALTER TYPE evidence_locator_type ADD VALUE IF NOT EXISTS 'text_byte_span';
ALTER TYPE evidence_locator_type ADD VALUE IF NOT EXISTS 'xml_element';
ALTER TYPE evidence_locator_type ADD VALUE IF NOT EXISTS 'pdf_page_block';
ALTER TYPE evidence_locator_type ADD VALUE IF NOT EXISTS 'pdf_region';
ALTER TYPE evidence_locator_type ADD VALUE IF NOT EXISTS 'office_paragraph';
ALTER TYPE evidence_locator_type ADD VALUE IF NOT EXISTS 'office_table_cell';
ALTER TYPE evidence_locator_type ADD VALUE IF NOT EXISTS 'spreadsheet_cell';
ALTER TYPE evidence_locator_type ADD VALUE IF NOT EXISTS 'slide_shape';
ALTER TYPE evidence_locator_type ADD VALUE IF NOT EXISTS 'slide_notes';
ALTER TYPE evidence_locator_type ADD VALUE IF NOT EXISTS 'email_header';
ALTER TYPE evidence_locator_type ADD VALUE IF NOT EXISTS 'email_mime_part';
ALTER TYPE evidence_locator_type ADD VALUE IF NOT EXISTS 'email_attachment';
ALTER TYPE evidence_locator_type ADD VALUE IF NOT EXISTS 'calendar_component';
ALTER TYPE evidence_locator_type ADD VALUE IF NOT EXISTS 'vcard_property';
ALTER TYPE evidence_locator_type ADD VALUE IF NOT EXISTS 'video_frame';
ALTER TYPE evidence_locator_type ADD VALUE IF NOT EXISTS 'subtitle_cue';
ALTER TYPE evidence_locator_type ADD VALUE IF NOT EXISTS 'geospatial_feature';
ALTER TYPE evidence_locator_type ADD VALUE IF NOT EXISTS 'database_table_row';
ALTER TYPE evidence_locator_type ADD VALUE IF NOT EXISTS 'database_cell';

