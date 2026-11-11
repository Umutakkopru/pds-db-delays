-- Feature table of scenario A: one row per modelling departure.
--
-- Placeholders filled by src/04_features.py:
--   {clean}     relation with the cleaned departures (step 2)
--   {weather}   relation with hourly weather, key local_hour (step 3)
--   {calendar}  relation with the daily calendar, key service_date (step 3)
--   {first_back}, {last_back}  history window in days before the departure day:
--                              service dates D - first_back ... D - last_back
--   {min_rows}  minimum number of departures in a window for a rate to be used
--   {row_filter}  which cleaned rows the table contains (default: the modelling rows)
--
-- Leakage rule 2 (CLAUDE.md): history for day D uses only departures planned
-- before D - 1 00:00. The window below ends at D - {last_back}; the departure day
-- and the day before it never enter. tests/test_features.py checks this by
-- changing later labels and comparing the result (time-travel test).

WITH keyed AS (
    SELECT *,
           hour(departure_planned_time)                   AS planned_hour,
           isodow(departure_planned_time) - 1             AS weekday,        -- 0 = Monday
           -- "route": the line for regional trains, the destination for all others
           COALESCE(line_id, final_destination_station)   AS route_key
    FROM {clean}
),
-- Rows of the output table. Normally the modelling rows; for the sensitivity
-- checks (D9, D18) the cancelled departures and those without timetable record.
m AS (
    SELECT * FROM keyed WHERE {row_filter}
),
-- Only modelling rows feed the history, whatever the output rows are.
hist_source AS (
    SELECT * FROM keyed WHERE exclude_reason IS NULL
),
-- Daily counts per key; the window then sums the days D - first_back ... D - last_back.
-- The UNION adds an empty (key, day) for every output row, so that an output row
-- gets its window even when no modelling departure shares its key on that day.
day_service_hour AS (
    SELECT service, planned_hour, service_date, SUM(n) AS n, SUM(d) AS d
    FROM (SELECT service, planned_hour, service_date, COUNT(*) AS n, SUM(delayed) AS d FROM hist_source GROUP BY 1, 2, 3
          UNION ALL
          SELECT DISTINCT service, planned_hour, service_date, 0, 0 FROM m)
    GROUP BY 1, 2, 3
),
hist_service_hour AS (
    SELECT service, planned_hour, service_date,
           SUM(n) OVER w AS n_hist, SUM(d) OVER w AS d_hist
    FROM day_service_hour
    WINDOW w AS (PARTITION BY service, planned_hour ORDER BY service_date
                 RANGE BETWEEN INTERVAL {first_back} DAY PRECEDING AND INTERVAL {last_back} DAY PRECEDING)
),
day_route AS (
    SELECT service, route_key, service_date, SUM(n) AS n, SUM(d) AS d
    FROM (SELECT service, route_key, service_date, COUNT(*) AS n, SUM(delayed) AS d FROM hist_source GROUP BY 1, 2, 3
          UNION ALL
          SELECT DISTINCT service, route_key, service_date, 0, 0 FROM m)
    GROUP BY 1, 2, 3
),
hist_route AS (
    SELECT service, route_key, service_date,
           SUM(n) OVER w AS n_hist, SUM(d) OVER w AS d_hist
    FROM day_route
    WINDOW w AS (PARTITION BY service, route_key ORDER BY service_date
                 RANGE BETWEEN INTERVAL {first_back} DAY PRECEDING AND INTERVAL {last_back} DAY PRECEDING)
),
day_all AS (
    SELECT service_date, SUM(n) AS n, SUM(d) AS d
    FROM (SELECT service_date, COUNT(*) AS n, SUM(delayed) AS d FROM hist_source GROUP BY 1
          UNION ALL
          SELECT DISTINCT service_date, 0, 0 FROM m)
    GROUP BY 1
),
hist_all AS (
    SELECT service_date, SUM(n) OVER w AS n_hist, SUM(d) OVER w AS d_hist
    FROM day_all
    WINDOW w AS (ORDER BY service_date
                 RANGE BETWEEN INTERVAL {first_back} DAY PRECEDING AND INTERVAL {last_back} DAY PRECEDING)
)
SELECT
    -- keys, split labels and the target (not features)
    m.id, m.service_date, m.departure_planned_time, m.split_a, m.split_b, m.delayed,
    -- timetable
    m.service,
    m.line_id,
    m.final_destination_station                                              AS destination,
    m.planned_hour,
    m.weekday,
    m.is_through,
    m.train_line_station_num                                                 AS stop_position,
    (epoch(m.departure_planned_time) - epoch(m.arrival_planned_time)) / 60   AS dwell_min,
    -- calendar
    c.is_public_holiday, c.is_school_holiday, c.is_bridge_day,
    -- weather at the planned departure hour (observed, stands in for a forecast)
    w.temperature_c, w.precipitation_mm, w.wind_speed_kmh, w.wind_gust_kmh, w.snowfall_cm, w.snow_depth_m,
    -- history: delay rates of the 28 days that end two days before the departure
    CASE WHEN hs.n_hist >= {min_rows} THEN hs.d_hist / hs.n_hist END          AS hist_rate_service_hour,
    CASE WHEN hr.n_hist >= {min_rows} THEN hr.d_hist / hr.n_hist END          AS hist_rate_route,
    COALESCE(hr.n_hist, 0)                                                    AS hist_n_route,
    CASE WHEN ha.n_hist >= {min_rows} THEN ha.d_hist / ha.n_hist END          AS hist_rate_all
FROM m
LEFT JOIN {calendar} c ON c.service_date = m.service_date
LEFT JOIN {weather}  w ON w.local_hour = date_trunc('hour', m.departure_planned_time)
LEFT JOIN hist_service_hour hs ON hs.service = m.service AND hs.planned_hour = m.planned_hour AND hs.service_date = m.service_date
LEFT JOIN hist_route hr        ON hr.service = m.service AND hr.route_key = m.route_key AND hr.service_date = m.service_date
LEFT JOIN hist_all ha          ON ha.service_date = m.service_date
ORDER BY m.departure_planned_time, m.id
