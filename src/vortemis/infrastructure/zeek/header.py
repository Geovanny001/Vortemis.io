ZEEK_CONN_HEADER: tuple[str, ...] = (
    "#separator \\x09",
    "#set_separator\t,",
    "#empty_field\t(empty)",
    "#unset_field\t-",
    "#path\tconn",
    "#open\t2026-11-05-00-00-00",
    "#fields\tts\tuid\tid.orig_h\tid.orig_p\tid.resp_h\tid.resp_p\tproto\tservice\tduration\torig_bytes\tresp_bytes\tconn_state",
    "#types\ttime\tstring\taddr\tport\taddr\tport\tenum\tstring\tinterval\tcount\tcount\tstring",
)
