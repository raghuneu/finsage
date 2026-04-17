-- Date dimension: calendar spine from 2020-01-01 to today

WITH RECURSIVE date_spine (date_day) AS (
    SELECT CAST('2020-01-01' AS DATE) AS date_day
    UNION ALL
    SELECT DATEADD(day, 1, date_day)
    FROM date_spine
    WHERE date_day < CURRENT_DATE()
)

SELECT
    date_day,
    YEAR(date_day)                                      AS year,
    QUARTER(date_day)                                   AS quarter,
    MONTH(date_day)                                     AS month,
    MONTHNAME(date_day)                                 AS month_name,
    WEEKOFYEAR(date_day)                                AS week_of_year,
    DAYOFWEEK(date_day)                                 AS day_of_week,
    DAYNAME(date_day)                                   AS day_name,
    CASE WHEN DAYOFWEEK(date_day) IN (0, 6) THEN TRUE ELSE FALSE END   AS is_weekend,
    CASE WHEN DAYOFWEEK(date_day) IN (0, 6) THEN FALSE ELSE TRUE END   AS is_trading_day
FROM date_spine
