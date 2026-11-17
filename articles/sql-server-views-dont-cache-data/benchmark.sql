/*
SQL SERVER VIEWS & COMPUTED COLUMNS — CONTROLLED BENCHMARK HARNESS
Companion to: "SQL Server Views Don't Cache Data — So When Are They Actually Faster?"
Draft created 2026-11-17. UNEXECUTED: verify on SQL Server 2025 / 2022 before reporting results.

Run ONLY in an isolated disposable development database. The script DROPS and recreates
objects starting with dbo.ViewBench_. Do not use on production or shared infrastructure.

Test design: six separate copies of the exact same rows, matching clustered PKs.
   1. ViewBench_Base                Direct expressions, no extra index
   2. ViewBench_Regular             Ordinary view, no extra index
   3. ViewBench_Indexed             Indexed view + index on parsed Code
   4. ViewBench_ComputedVirtual     Nonpersisted computed columns, no extra index
   5. ViewBench_ComputedIndexed     Indexed nonpersisted computed columns
   6. ViewBench_ComputedPersisted   Indexed persisted computed columns

Test uses simple valid strings like CODE0042|ACTIVE (one delimiter only).
Dataset count default 100,000; increase @RowCount to up to 1,000,000 for a bigger test.

Important: This is an example harness, NOT a peer-reviewed or already executed benchmark.
Capturing median times across repeated randomized runs is left to the experimenter.
*/

-- Set USE [YourDisposableDatabase]; before running.
IF DB_NAME() IN (N'master', N'model', N'msdb', N'tempdb')
    THROW 51000, 'Choose a disposable USER database before running this harness.', 1;
GO

SET ANSI_NULLS ON;
SET ANSI_PADDING ON;
SET ANSI_WARNINGS ON;
SET ARITHABORT ON;
SET CONCAT_NULL_YIELDS_NULL ON;
SET QUOTED_IDENTIFIER ON;
SET NUMERIC_ROUNDABORT OFF;
GO

-- ENVIRONMENT: paste output into your benchmark report.
SELECT
    @@VERSION AS FullVersion,
    SERVERPROPERTY('ProductVersion') AS Build,
    SERVERPROPERTY('Edition') AS Edition,
    SERVERPROPERTY('ProductUpdateLevel') AS ProductUpdateLevel,
    SERVERPROPERTY('ProductLevel') AS ProductLevel,
    DB_NAME() AS DatabaseName,
    d.compatibility_level,
    d.collation_name
FROM sys.databases AS d
WHERE d.database_id = DB_ID();
GO

-- CLEAN-UP ONLY OUR TEST OBJECTS
IF OBJECT_ID(N'dbo.ViewBench_vIndexed', N'V') IS NOT NULL
    DROP VIEW dbo.ViewBench_vIndexed;
IF OBJECT_ID(N'dbo.ViewBench_vRegular', N'V') IS NOT NULL
    DROP VIEW dbo.ViewBench_vRegular;
GO
IF OBJECT_ID(N'dbo.ViewBench_Base', N'U') IS NOT NULL DROP TABLE dbo.ViewBench_Base;
IF OBJECT_ID(N'dbo.ViewBench_Regular', N'U') IS NOT NULL DROP TABLE dbo.ViewBench_Regular;
IF OBJECT_ID(N'dbo.ViewBench_Indexed', N'U') IS NOT NULL DROP TABLE dbo.ViewBench_Indexed;
IF OBJECT_ID(N'dbo.ViewBench_ComputedVirtual', N'U') IS NOT NULL DROP TABLE dbo.ViewBench_ComputedVirtual;
IF OBJECT_ID(N'dbo.ViewBench_ComputedIndexed', N'U') IS NOT NULL DROP TABLE dbo.ViewBench_ComputedIndexed;
IF OBJECT_ID(N'dbo.ViewBench_ComputedPersisted', N'U') IS NOT NULL DROP TABLE dbo.ViewBench_ComputedPersisted;
GO

CREATE TABLE dbo.ViewBench_Base
(
    DocumentId int NOT NULL CONSTRAINT PK_ViewBench_Base PRIMARY KEY CLUSTERED,
    CompositeValue nvarchar(100) NOT NULL
);
GO

DECLARE @RowCount int = 100000; -- Change to 1000000 for an extended run.

;WITH Digits AS
(
    SELECT n FROM (VALUES(0),(1),(2),(3),(4),(5),(6),(7),(8),(9)) AS v(n)
),
N AS
(
    SELECT TOP (@RowCount)
        ROW_NUMBER() OVER (ORDER BY a.n, b.n, c.n, d.n, e.n, f.n) AS n
    FROM Digits AS a
    CROSS JOIN Digits AS b
    CROSS JOIN Digits AS c
    CROSS JOIN Digits AS d
    CROSS JOIN Digits AS e
    CROSS JOIN Digits AS f
)
INSERT dbo.ViewBench_Base (DocumentId, CompositeValue)
SELECT CAST(n AS int),
       CONCAT(
           N'CODE', RIGHT(N'0000' + CONVERT(nvarchar(10), n % 1000), 4),
           N'|',
           CASE WHEN n % 2 = 0 THEN N'ACTIVE' ELSE N'INACTIVE' END
       )
FROM N;
GO

-- The copies have the same data and the same starting clustered primary key.
SELECT DocumentId, CompositeValue INTO dbo.ViewBench_Regular FROM dbo.ViewBench_Base;
SELECT DocumentId, CompositeValue INTO dbo.ViewBench_Indexed FROM dbo.ViewBench_Base;
SELECT DocumentId, CompositeValue INTO dbo.ViewBench_ComputedVirtual FROM dbo.ViewBench_Base;
SELECT DocumentId, CompositeValue INTO dbo.ViewBench_ComputedIndexed FROM dbo.ViewBench_Base;
SELECT DocumentId, CompositeValue INTO dbo.ViewBench_ComputedPersisted FROM dbo.ViewBench_Base;
GO

ALTER TABLE dbo.ViewBench_Regular ADD CONSTRAINT PK_ViewBench_Regular PRIMARY KEY CLUSTERED (DocumentId);
ALTER TABLE dbo.ViewBench_Indexed ADD CONSTRAINT PK_ViewBench_Indexed PRIMARY KEY CLUSTERED (DocumentId);
ALTER TABLE dbo.ViewBench_ComputedVirtual ADD CONSTRAINT PK_ViewBench_ComputedVirtual PRIMARY KEY CLUSTERED (DocumentId);
ALTER TABLE dbo.ViewBench_ComputedIndexed ADD CONSTRAINT PK_ViewBench_ComputedIndexed PRIMARY KEY CLUSTERED (DocumentId);
ALTER TABLE dbo.ViewBench_ComputedPersisted ADD CONSTRAINT PK_ViewBench_ComputedPersisted PRIMARY KEY CLUSTERED (DocumentId);
GO

-- REGULAR VIEW
CREATE VIEW dbo.ViewBench_vRegular
AS
SELECT
    DocumentId,
    LEFT(CompositeValue, CHARINDEX(N'|', CompositeValue) - 1) AS Code,
    SUBSTRING(CompositeValue, CHARINDEX(N'|', CompositeValue) + 1, 100) AS Status
FROM dbo.ViewBench_Regular;
GO

-- INDEXED VIEW
CREATE VIEW dbo.ViewBench_vIndexed
WITH SCHEMABINDING
AS
SELECT
    DocumentId,
    LEFT(CompositeValue, CHARINDEX(N'|', CompositeValue) - 1) AS Code,
    SUBSTRING(CompositeValue, CHARINDEX(N'|', CompositeValue) + 1, 100) AS Status
FROM dbo.ViewBench_Indexed;
GO
CREATE UNIQUE CLUSTERED INDEX CIX_ViewBench_vIndexed
ON dbo.ViewBench_vIndexed (DocumentId);
GO
CREATE NONCLUSTERED INDEX IX_ViewBench_vIndexed_Code
ON dbo.ViewBench_vIndexed (Code)
INCLUDE (Status);
GO

-- NONPERSISTED, NOT INDEXED
ALTER TABLE dbo.ViewBench_ComputedVirtual ADD
    Code AS LEFT(CompositeValue, CHARINDEX(N'|', CompositeValue) - 1),
    Status AS SUBSTRING(CompositeValue, CHARINDEX(N'|', CompositeValue) + 1, 100);
GO

-- NONPERSISTED, INDEXED
ALTER TABLE dbo.ViewBench_ComputedIndexed ADD
    Code AS LEFT(CompositeValue, CHARINDEX(N'|', CompositeValue) - 1),
    Status AS SUBSTRING(CompositeValue, CHARINDEX(N'|', CompositeValue) + 1, 100);
GO
CREATE NONCLUSTERED INDEX IX_ViewBench_ComputedIndexed_Code
ON dbo.ViewBench_ComputedIndexed (Code)
INCLUDE (Status);
GO

-- PERSISTED, INDEXED
ALTER TABLE dbo.ViewBench_ComputedPersisted ADD
    Code AS LEFT(CompositeValue, CHARINDEX(N'|', CompositeValue) - 1) PERSISTED,
    Status AS SUBSTRING(CompositeValue, CHARINDEX(N'|', CompositeValue) + 1, 100) PERSISTED;
GO
CREATE NONCLUSTERED INDEX IX_ViewBench_ComputedPersisted_Code
ON dbo.ViewBench_ComputedPersisted (Code)
INCLUDE (Status);
GO

-- CHECK PARSER ELIGIBILITY AND DATA EQUIVALENCE
SELECT
    COLUMNPROPERTY(OBJECT_ID(N'dbo.ViewBench_ComputedIndexed'), N'Code', 'IsDeterministic') AS CodeIsDeterministic,
    COLUMNPROPERTY(OBJECT_ID(N'dbo.ViewBench_ComputedIndexed'), N'Code', 'IsPrecise') AS CodeIsPrecise,
    COLUMNPROPERTY(OBJECT_ID(N'dbo.ViewBench_ComputedPersisted'), N'Code', 'IsDeterministic') AS PersistedCodeIsDeterministic;

SELECT N'Base' AS Configuration, COUNT_BIG(*) AS Rows FROM dbo.ViewBench_Base
UNION ALL SELECT N'Regular', COUNT_BIG(*) FROM dbo.ViewBench_Regular
UNION ALL SELECT N'IndexedView', COUNT_BIG(*) FROM dbo.ViewBench_Indexed
UNION ALL SELECT N'ComputedVirtual', COUNT_BIG(*) FROM dbo.ViewBench_ComputedVirtual
UNION ALL SELECT N'ComputedIndexed', COUNT_BIG(*) FROM dbo.ViewBench_ComputedIndexed
UNION ALL SELECT N'ComputedPersisted', COUNT_BIG(*) FROM dbo.ViewBench_ComputedPersisted;
GO

/* READ BENCHMARKS
   Enable Actual Execution Plan (SSMS: Ctrl+M).
   Repeat query families many times in varied order; capture CPU, elapsed,
   logical reads, plan shape, and row counts. Do not interpret one timing as a benchmark.
*/
SET STATISTICS IO ON;
SET STATISTICS TIME ON;
GO

DECLARE @Code nvarchar(100) = N'CODE0042';

-- Selective filter: same logical result, six physical designs.
SELECT COUNT_BIG(*) AS Matches
FROM dbo.ViewBench_Base
WHERE LEFT(CompositeValue, CHARINDEX(N'|', CompositeValue) - 1) = @Code
OPTION (RECOMPILE);

SELECT COUNT_BIG(*) AS Matches
FROM dbo.ViewBench_vRegular
WHERE Code = @Code
OPTION (RECOMPILE);

SELECT COUNT_BIG(*) AS Matches
FROM dbo.ViewBench_vIndexed WITH (NOEXPAND)
WHERE Code = @Code
OPTION (RECOMPILE);

SELECT COUNT_BIG(*) AS Matches
FROM dbo.ViewBench_ComputedVirtual
WHERE Code = @Code
OPTION (RECOMPILE);

SELECT COUNT_BIG(*) AS Matches
FROM dbo.ViewBench_ComputedIndexed
WHERE Code = @Code
OPTION (RECOMPILE);

SELECT COUNT_BIG(*) AS Matches
FROM dbo.ViewBench_ComputedPersisted
WHERE Code = @Code
OPTION (RECOMPILE);
GO

-- Low-selectivity filter: no targeted index on Status, deliberately.
SELECT COUNT_BIG(*) AS Matches FROM dbo.ViewBench_Base WHERE SUBSTRING(CompositeValue, CHARINDEX(N'|', CompositeValue) + 1, 100) = N'ACTIVE' OPTION (RECOMPILE);
SELECT COUNT_BIG(*) AS Matches FROM dbo.ViewBench_vRegular WHERE Status = N'ACTIVE' OPTION (RECOMPILE);
SELECT COUNT_BIG(*) AS Matches FROM dbo.ViewBench_vIndexed WITH (NOEXPAND) WHERE Status = N'ACTIVE' OPTION (RECOMPILE);
SELECT COUNT_BIG(*) AS Matches FROM dbo.ViewBench_ComputedVirtual WHERE Status = N'ACTIVE' OPTION (RECOMPILE);
SELECT COUNT_BIG(*) AS Matches FROM dbo.ViewBench_ComputedIndexed WHERE Status = N'ACTIVE' OPTION (RECOMPILE);
SELECT COUNT_BIG(*) AS Matches FROM dbo.ViewBench_ComputedPersisted WHERE Status = N'ACTIVE' OPTION (RECOMPILE);
GO

-- Targeted point lookups. Output should be identical across designs.
SELECT DocumentId,
       LEFT(CompositeValue, CHARINDEX(N'|', CompositeValue) - 1) AS Code,
       SUBSTRING(CompositeValue, CHARINDEX(N'|', CompositeValue) + 1, 100) AS Status
FROM dbo.ViewBench_Base WHERE DocumentId = 4242;
SELECT DocumentId, Code, Status FROM dbo.ViewBench_vRegular WHERE DocumentId = 4242;
SELECT DocumentId, Code, Status FROM dbo.ViewBench_vIndexed WITH (NOEXPAND) WHERE DocumentId = 4242;
SELECT DocumentId, Code, Status FROM dbo.ViewBench_ComputedVirtual WHERE DocumentId = 4242;
SELECT DocumentId, Code, Status FROM dbo.ViewBench_ComputedIndexed WHERE DocumentId = 4242;
SELECT DocumentId, Code, Status FROM dbo.ViewBench_ComputedPersisted WHERE DocumentId = 4242;
GO

SET STATISTICS IO OFF;
SET STATISTICS TIME OFF;
GO

-- Approximate allocated index space; do not compare just row count.
-- Requires appropriate DMV permissions on some SQL Server installations.
SELECT
    OBJECT_SCHEMA_NAME(p.object_id) AS ObjectSchema,
    OBJECT_NAME(p.object_id) AS ObjectName,
    i.name AS IndexName,
    p.index_id,
    SUM(p.used_page_count) * 8.0 / 1024.0 AS UsedMB
FROM sys.dm_db_partition_stats AS p
JOIN sys.indexes AS i
    ON i.object_id = p.object_id AND i.index_id = p.index_id
WHERE OBJECT_NAME(p.object_id) LIKE N'ViewBench_%'
GROUP BY p.object_id, p.index_id, i.name
ORDER BY ObjectName, p.index_id;
GO

/* WRITE-AMPLIFICATION TEST PLAN (run separately; don't conflate with read runs)
   For each table, use the same document ID range, exact value transformation,
   explicit transaction, and comparable server/load conditions.

   Example for the direct baseline (repeat for the 5 other TABLES):

   BEGIN TRAN;
       UPDATE dbo.ViewBench_Base
          SET CompositeValue = N'CODE0042|PENDING'
        WHERE DocumentId BETWEEN 20001 AND 21000;
   ROLLBACK;

   Repeat the UPDATE (and separate INSERT/DELETE tests) under STATISTICS IO/TIME,
   record log bytes and index pages if permitted, and report medians.
   Indexed view and computed-column indexes have maintenance work on writes.
*/