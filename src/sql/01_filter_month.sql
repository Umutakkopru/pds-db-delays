-- Filter one monthly file to Würzburg Hbf plus the earlier stops of the same trips.
--
-- Placeholders filled by src/01_download.py:
--   {source}   path of the monthly Parquet file
--   {station}  'Würzburg Hbf'
--   {month}    'YYYY-MM' of the source file
--
-- Output: one row per stop with three extra columns
--   row_role      'wuerzburg' or 'earlier_stop'
--   wuerzburg_id  id of the Würzburg row the stop belongs to
--   source_month  month of the file the row came from (a file can contain a
--                 few rows planned on the last day of the previous month)
--
-- A single trip = train_line_ride_id + day: the ride ID repeats on every day of
-- the month, so earlier stops must lie in the 12 hours before the Würzburg
-- arrival (this also handles trips that cross midnight).

WITH f AS (
    SELECT * FROM read_parquet('{source}')
),
w AS (
    SELECT * FROM f
    WHERE station_name = '{station}'
),
anchor AS (
    -- Only trains that arrive at Würzburg can have earlier stops.
    SELECT id                     AS wuerzburg_id,
           train_line_ride_id     AS ride,
           train_line_station_num AS w_num,
           arrival_planned_time   AS w_arr
    FROM w
    WHERE arrival_planned_time IS NOT NULL
),
prev AS (
    SELECT a.wuerzburg_id, f.*
    FROM anchor a
    JOIN f
      ON  f.train_line_ride_id = a.ride
      AND f.train_line_station_num < a.w_num
      AND COALESCE(f.departure_planned_time, f.arrival_planned_time) <  a.w_arr
      AND COALESCE(f.departure_planned_time, f.arrival_planned_time) >= a.w_arr - INTERVAL 12 HOUR
    WHERE f.station_name <> '{station}'
)
SELECT 'wuerzburg' AS row_role, '{month}' AS source_month, id AS wuerzburg_id, * FROM w
UNION ALL BY NAME
SELECT 'earlier_stop' AS row_role, '{month}' AS source_month, * FROM prev
