SELECT loan_status, count(*) AS loans,
    100.0 * count(*) / sum(count(*)) OVER () AS pct_of_loans
FROM loans GROUP BY loan_status ORDER BY loans DESC;
