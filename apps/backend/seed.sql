-- Seed Phase 1 : 23 niches + 6 marches (rejouable)
-- psql -U scalelab -d scalelab -h localhost -f seed.sql

INSERT INTO niches (label) VALUES
  ('Fitness'),('Fashion'),('Cosplay'),('Gamer'),('Lifestyle'),
  ('Model'),('Travel'),('Artistic'),('Alt/Goth'),('Luxury'),
  ('ASMR'),('Dance'),('Comedy'),('Couple'),('Feet'),
  ('Curvy'),('Petite'),('Mature'),('Latina'),('Asian'),
  ('Ebony'),('Redhead'),('Blonde')
ON CONFLICT (label) DO NOTHING;

INSERT INTO marches (code, label, langue, fuseau) VALUES
  ('US', 'United States', 'en', 'America/New_York'),
  ('UK', 'United Kingdom', 'en', 'Europe/London'),
  ('FR', 'France', 'fr', 'Europe/Paris'),
  ('DE', 'Germany', 'de', 'Europe/Berlin'),
  ('AU', 'Australia', 'en', 'Australia/Sydney'),
  ('CA', 'Canada', 'en', 'America/Toronto')
ON CONFLICT (code) DO NOTHING;
