from vortemis.entrypoints.cli import BANNER, CREDITS, print_banner


def test_print_banner_prints_banner_and_credits(capsys) -> None:
    print_banner()
    captured = capsys.readouterr().out

    assert BANNER in captured
    assert CREDITS in captured
