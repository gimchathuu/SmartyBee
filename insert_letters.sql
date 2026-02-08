-- Insert additional Sinhala letters into the database
INSERT INTO letter_template (LetterID, SinhalaChar, StrokePathJSON, DifficultyLevel, ImageURL, ExampleWords) VALUES
-- ---------------- VOWELS ----------------
(8, 'ඊ', '[{"x": 0.5, "y": 0.2}, {"x": 0.5, "y": 0.8}]', 'Easy', '/static/images/letters/ii.png', '["ඊතලය", "ඊයේ", "ඊයම්"]'),
(9, 'උ', '[{"x": 0.5, "y": 0.2}, {"x": 0.5, "y": 0.8}]', 'Easy', '/static/images/letters/u.png', '["උයන", "උදෑසන", "උගුල"]'),
(10, 'ඌ', '[{"x": 0.5, "y": 0.2}, {"x": 0.5, "y": 0.8}]', 'Easy', '/static/images/letters/uu.png', '["ඌරා", "ඌරුමීයා", "ඌෂ්ණ"]'),
(11, 'එ', '[{"x": 0.5, "y": 0.2}, {"x": 0.5, "y": 0.8}]', 'Easy', '/static/images/letters/e.png', '["එළුවා", "එළිය", "එළවළු"]'),
(12, 'ඒ', '[{"x": 0.5, "y": 0.2}, {"x": 0.5, "y": 0.8}]', 'Easy', '/static/images/letters/ee.png', '["ඒක", "ඒරා", "ඒකා"]'),
(13, 'ඔ', '[{"x": 0.5, "y": 0.2}, {"x": 0.5, "y": 0.8}]', 'Easy', '/static/images/letters/o.png', '["ඔරුව", "ඔරලෝසුව", "ඔළුව"]'),
(14, 'ඕ', '[{"x": 0.5, "y": 0.2}, {"x": 0.5, "y": 0.8}]', 'Easy', '/static/images/letters/oo.png', '["ඕලු", "ඕනෑ", "ඕවිට"]'),

-- ---------------- CONSONANTS ----------------
(15, 'ක', '[{"x": 0.5, "y": 0.2}, {"x": 0.5, "y": 0.8}]', 'Medium', '/static/images/letters/ka.png', '["කලය", "කළුවර", "කතන්දර"]'),
(16, 'ග', '[{"x": 0.5, "y": 0.2}, {"x": 0.5, "y": 0.8}]', 'Medium', '/static/images/letters/ga.png', '["ගස", "ගෙදර", "ගම"]'),
(17, 'ට', '[{"x": 0.5, "y": 0.2}, {"x": 0.5, "y": 0.8}]', 'Medium', '/static/images/letters/ta.png', '["ටකය", "ටකරන්", "ටක්"]'),
(18, 'ඩ', '[{"x": 0.5, "y": 0.2}, {"x": 0.5, "y": 0.8}]', 'Medium', '/static/images/letters/da.png', '["ඩය", "ඩබල්", "ඩක්"]'),
(19, 'ණ', '[{"x": 0.5, "y": 0.2}, {"x": 0.5, "y": 0.8}]', 'Medium', '/static/images/letters/na_mur.png', '["වීණාව", "මුහුණ", "ගුණය"]'),
(20, 'ත', '[{"x": 0.5, "y": 0.2}, {"x": 0.5, "y": 0.8}]', 'Medium', '/static/images/letters/tha.png', '["තරුව", "තල", "තනකොළ"]'),
(21, 'ද', '[{"x": 0.5, "y": 0.2}, {"x": 0.5, "y": 0.8}]', 'Medium', '/static/images/letters/dha.png', '["දත", "දවස", "දඩයම"]'),
(22, 'න', '[{"x": 0.5, "y": 0.2}, {"x": 0.5, "y": 0.8}]', 'Medium', '/static/images/letters/na.png', '["නළල", "නරියා", "නළුවා"]'),
(23, 'ප', '[{"x": 0.5, "y": 0.2}, {"x": 0.5, "y": 0.8}]', 'Medium', '/static/images/letters/pa.png', '["පෑන", "පළතුර", "පනාව"]'),
(24, 'බ', '[{"x": 0.5, "y": 0.2}, {"x": 0.5, "y": 0.8}]', 'Medium', '/static/images/letters/ba.png', '["බඩගිනි", "බර", "බලලා"]'),
(25, 'ම', '[{"x": 0.5, "y": 0.2}, {"x": 0.5, "y": 0.8}]', 'Medium', '/static/images/letters/ma.png', '["මල", "මහත", "මහත්තයා"]'),
(26, 'ය', '[{"x": 0.5, "y": 0.2}, {"x": 0.5, "y": 0.8}]', 'Medium', '/static/images/letters/ya.png', '["යහන", "යතුර", "යව"]'),
(27, 'ර', '[{"x": 0.5, "y": 0.2}, {"x": 0.5, "y": 0.8}]', 'Medium', '/static/images/letters/ra.png', '["රස", "රජා", "රබර්"]'),
(28, 'ච', '[{"x": 0.5, "y": 0.2}, {"x": 0.5, "y": 0.8}]', 'Medium', '/static/images/letters/cha.png', '["චකිතය", "චපල", "චතුර"]'),
(29, 'ජ', '[{"x": 0.5, "y": 0.2}, {"x": 0.5, "y": 0.8}]', 'Medium', '/static/images/letters/ja.png', '["ජලය", "ජය", "ජවය"]'),
(30, 'ල', '[{"x": 0.5, "y": 0.2}, {"x": 0.5, "y": 0.8}]', 'Medium', '/static/images/letters/la.png', '["ලපය", "ළමයා", "ලියුම"]'),
(31, 'ව', '[{"x": 0.5, "y": 0.2}, {"x": 0.5, "y": 0.8}]', 'Medium', '/static/images/letters/va.png', '["වතුර", "වඳුරා", "වත්ත"]'),
(32, 'ස', '[{"x": 0.5, "y": 0.2}, {"x": 0.5, "y": 0.8}]', 'Medium', '/static/images/letters/sa.png', '["සමනලයා", "සතා", "සිනහව"]'),
(33, 'හ', '[{"x": 0.5, "y": 0.2}, {"x": 0.5, "y": 0.8}]', 'Medium', '/static/images/letters/ha.png', '["හඳ", "හාවා", "හයිය"]'),
(34, 'ළ', '[{"x": 0.5, "y": 0.2}, {"x": 0.5, "y": 0.8}]', 'Hard', '/static/images/letters/lla.png', '["ළිඳ", "ළය", "ළැම"]');
