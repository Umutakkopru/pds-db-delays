-- Feature table of scenario B: scenario A features plus the delays at earlier stops.
--
-- Placeholders filled by src/04_features.py:
--   {features_a}  relation with the scenario A feature table
--   {clean}       relation with the cleaned departures (for the scenario B row filter)
--   {prev}        relation with the earlier stops (step 2)
--
-- Rows: through trains with a usable earlier stop inside a scenario B split (D20).
-- Leakage rule 3: only stops the train has already passed. Earlier stops are
-- planned before the Würzburg arrival (step 1); the prediction moment is the
-- departure from the previous stop, so its delay and the delays before it are known.

WITH usable AS (
    -- earlier stops that give a delay: not cancelled, with a reported time
    SELECT wuerzburg_id, stop_delay, train_line_station_num,
           COALESCE(departure_planned_time, arrival_planned_time) AS stop_planned,
           row_number() OVER (PARTITION BY wuerzburg_id
                              ORDER BY COALESCE(departure_planned_time, arrival_planned_time) DESC, id) AS rn
    FROM {prev}
    WHERE NOT stop_canceled AND stop_delay IS NOT NULL
),
rows_b AS (
    SELECT id, train_line_station_num
    FROM {clean}
    WHERE exclude_reason IS NULL AND is_through AND has_prev_stop AND split_b IS NOT NULL
)
SELECT a.*,
       p1.stop_delay                                                          AS prev_delay,
       p2.stop_delay                                                          AS prev_delay_2,
       (epoch(a.departure_planned_time) - epoch(p1.stop_planned)) / 60        AS prev_minutes_to_departure,
       CASE WHEN r.train_line_station_num > p1.train_line_station_num
            THEN r.train_line_station_num - p1.train_line_station_num - 1 END AS prev_stops_between
FROM {features_a} a
JOIN rows_b r        ON r.id = a.id
JOIN usable p1       ON p1.wuerzburg_id = a.id AND p1.rn = 1
LEFT JOIN usable p2  ON p2.wuerzburg_id = a.id AND p2.rn = 2
ORDER BY a.departure_planned_time, a.id
