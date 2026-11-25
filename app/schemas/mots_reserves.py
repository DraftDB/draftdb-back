"""Mots réservés de MySQL et de PostgreSQL (RG-10, cahier des charges § 3.3.1.4 et CU 2.5).

Un nom de table ou de colonne qui en fait partie n'est pas refusé : il reçoit un avertissement, car il
devra être protégé par des guillemets dans les scripts SQL. Refuser bloquerait l'import de dumps
réels (EX-14), où des noms comme « user » ou « order » sont courants.

Sources (relevées le 25/11/2026) :
- PostgreSQL 16 : ``SELECT word FROM pg_get_keywords() WHERE catcode IN ('R', 'T')``, soit les mots
  qui ne peuvent pas servir de nom de table ou de colonne sans guillemets (101 mots) ;
- MySQL 8.4 : mots marqués « (R) » dans la documentation officielle, page « Keywords and Reserved
  Words » (264 mots).
"""

MOTS_RESERVES_POSTGRESQL = frozenset("""
    all analyse analyze and any array as asc asymmetric authorization binary both case cast check
    collate collation column concurrently constraint create cross current_catalog current_date
    current_role current_schema current_time current_timestamp current_user default deferrable desc
    distinct do else end except false fetch for foreign freeze from full grant group having ilike in
    initially inner intersect into is isnull join lateral leading left like limit localtime
    localtimestamp natural not notnull null offset on only or order outer overlaps placing primary
    references returning right select session_user similar some symmetric system_user table
    tablesample then to trailing true union unique user using variadic verbose when where window
    with
""".split())

MOTS_RESERVES_MYSQL = frozenset("""
    accessible add all alter analyze and as asc asensitive before between bigint binary blob both by
    call cascade case change char character check collate column condition constraint continue
    convert create cross cube cume_dist current_date current_time current_timestamp current_user
    cursor database databases day_hour day_microsecond day_minute day_second dec decimal declare
    default delayed delete dense_rank desc describe deterministic distinct distinctrow div double
    drop dual each else elseif empty enclosed escaped except exists exit explain false fetch
    first_value float float4 float8 for force foreign from fulltext function generated get grant
    group grouping groups having high_priority hour_microsecond hour_minute hour_second if ignore in
    index infile inner inout insensitive insert int int1 int2 int3 int4 int8 integer intersect
    interval into io_after_gtids io_before_gtids is iterate join json_table key keys kill lag
    last_value lateral lead leading leave left like limit linear lines load localtime localtimestamp
    lock long longblob longtext loop low_priority master_bind master_ssl_verify_server_cert match
    maxvalue mediumblob mediumint mediumtext middleint minute_microsecond minute_second mod modifies
    natural no_write_to_binlog not nth_value ntile null numeric of on optimize optimizer_costs
    option optionally or order out outer outfile over partition percent_rank precision primary
    procedure purge qualify range rank read read_write reads real recursive references regexp
    release rename repeat replace require resignal restrict return revoke right rlike row row_number
    rows schema schemas second_microsecond select sensitive separator set show signal smallint
    spatial specific sql sql_big_result sql_calc_found_rows sql_small_result sqlexception sqlstate
    sqlwarning ssl starting stored straight_join system table tablesample terminated then tinyblob
    tinyint tinytext to trailing trigger true undo union unique unlock unsigned update usage use
    using utc_date utc_time utc_timestamp values varbinary varchar varcharacter varying virtual when
    where while window with write xor year_month zerofill
""".split())
