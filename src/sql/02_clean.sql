-- Clean the Würzburg rows: one row per planned departure, nothing deleted.
--
-- Placeholders filled by src/02_clean.py:
--   {files}            glob of data/interim/wuerzburg_*.parquet
--   {threshold}        delay threshold in minutes (config.DELAY_THRESHOLD_MIN)
--   {invalid_below}    delays below this are invalid (config.INVALID_DELAY_BELOW_MIN)
--   {dst_days}         list of DATE literals (config.dst_change_days())
--   {dst_from}, {dst_to}  excluded hours on those days, [from, to)
--   {split_a}, {split_b}  CASE expressions that name the split of a departure
--
-- Rules: decision log D2 (target), D7 and D19 (line_id, service, exclude_reason),
-- D8-D10 (exclusions), D20 (is_through, has_prev_stop).
-- Trains that end at Würzburg (no planned departure) are not part of the target
-- and are not in the output.

WITH src AS (
    SELECT * FROM read_parquet('{files}', union_by_name = true)
),
w AS (
    SELECT *,
           upper(replace(line_number, ' ', '')) AS line_norm,
           CASE WHEN train_type IN ('ICE', 'IC', 'EC')                THEN 'long_distance'
                WHEN train_type IN ('NJ', 'EN')                       THEN 'night'
                WHEN regexp_matches(train_type, '^(RE|RB|ARV|IRE)')   THEN 'regional'
                ELSE 'other' END AS service
    FROM src
    WHERE row_role = 'wuerzburg' AND departure_planned_time IS NOT NULL
),
-- Usual prefixed line of a train number, per line digits. Used only for
-- digit-only lines whose train type is not RE or RB (ARV rows in 2026).
line_votes AS (
    SELECT train_number, regexp_extract(line_norm, '[0-9]+$') AS digits, line_norm, COUNT(*) AS n
    FROM w
    WHERE service = 'regional' AND regexp_matches(line_norm, '^[A-Z]+[0-9]+$')
    GROUP BY 1, 2, 3
),
line_lookup AS (
    SELECT train_number, digits, line_norm AS usual_line
    FROM (SELECT *, row_number() OVER (PARTITION BY train_number, digits ORDER BY n DESC, line_norm) AS rn
          FROM line_votes)
    WHERE rn = 1
),
-- Earlier stops that can give a delay: not cancelled, with a reported time.
prev AS (
    SELECT wuerzburg_id, COUNT(*) AS n_prev_stops
    FROM src
    WHERE row_role = 'earlier_stop'
      AND NOT COALESCE(departure_is_canceled, FALSE)
      AND COALESCE(departure_change_time, arrival_change_time) IS NOT NULL
    GROUP BY 1
),
d AS (
    SELECT w.*,
           (epoch(w.departure_change_time) - epoch(w.departure_planned_time)) / 60 AS dep_delay,
           CAST(w.departure_planned_time AS DATE) AS service_date,
           row_number() OVER (PARTITION BY w.id ORDER BY w.source_month) AS id_copy,
           CASE WHEN w.service <> 'regional'                        THEN NULL
                WHEN regexp_matches(w.line_norm, '^[A-Z]+[0-9]+$')  THEN w.line_norm
                WHEN regexp_matches(w.line_norm, '^[0-9]+$') AND w.train_type IN ('RE', 'RB')
                                                                    THEN w.train_type || w.line_norm
                WHEN regexp_matches(w.line_norm, '^[0-9]+$')        THEN COALESCE(l.usual_line, 'RE' || w.line_norm)
                ELSE NULL END AS line_id,
           w.arrival_planned_time IS NOT NULL AS is_through,
           COALESCE(p.n_prev_stops, 0) > 0     AS has_prev_stop
    FROM w
    LEFT JOIN line_lookup l ON l.train_number = w.train_number AND l.digits = w.line_norm
    LEFT JOIN prev p        ON p.wuerzburg_id = w.id
)
SELECT * EXCLUDE (line_norm, id_copy, row_role),
       CAST(dep_delay >= {threshold} AS INTEGER) AS delayed,
       COALESCE(departure_is_canceled, FALSE)    AS canceled,
       -- first matching rule wins; NULL = modelling row
       CASE WHEN train_type = 'Bus'                                   THEN 'bus'
            WHEN NOT COALESCE(has_plan_record, FALSE)                 THEN 'no_plan_record'
            WHEN COALESCE(departure_is_canceled, FALSE)               THEN 'canceled'
            WHEN service_date IN ({dst_days})
                 AND hour(departure_planned_time) >= {dst_from}
                 AND hour(departure_planned_time) <  {dst_to}         THEN 'dst_night'
            WHEN dep_delay IS NULL OR dep_delay < {invalid_below}     THEN 'invalid_delay'
            WHEN id_copy > 1                                          THEN 'duplicate_id'
            END AS exclude_reason,
       {split_a} AS split_a,
       {split_b} AS split_b
FROM d
ORDER BY departure_planned_time, id
