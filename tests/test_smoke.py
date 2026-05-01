from auto_invest import main


def test_main_runs(capsys):
    main()
    captured = capsys.readouterr()
    assert "auto-invest" in captured.out
