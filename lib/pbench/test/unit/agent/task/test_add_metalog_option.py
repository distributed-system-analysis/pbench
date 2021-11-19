import configparser

from pbench.cli.agent.commands.log import add_metalog_option


class TestAddMetalogOption:
    @staticmethod
    def test_add_metalog_option(tmp_path):
        mdlog = tmp_path / "metadata.log"
        mdlog.write_text(
            """[existing]
            existing_option = 41
            """
        )
        # New section, new option
        add_metalog_option(mdlog, "new", "new_option", "420")

        cfg = configparser.ConfigParser()
        cfg.read(mdlog)

        sections = cfg.sections()
        assert len(sections) == 2

        options = cfg.options("new")
        assert len(options) == 1
        assert cfg.get("new", "new_option") == "420"

        options = cfg.options("existing")
        assert len(options) == 1
        assert cfg.get("existing", "existing_option") == "41"

        # Existing section, new option
        add_metalog_option(mdlog, "existing", "new_option", "142")

        cfg = configparser.ConfigParser()
        cfg.read(mdlog)

        sections = cfg.sections()
        assert len(sections) == 2

        options = cfg.options("new")
        assert len(options) == 1
        assert cfg.get("new", "new_option") == "420"

        options = cfg.options("existing")
        assert len(options) == 2
        assert cfg.get("existing", "new_option") == "142"
        assert cfg.get("existing", "existing_option") == "41"

        # Existing section, existing option
        add_metalog_option(mdlog, "existing", "existing_option", "42")

        cfg = configparser.ConfigParser()
        cfg.read(mdlog)

        sections = cfg.sections()
        assert len(sections) == 2

        options = cfg.options("new")
        assert len(options) == 1
        assert cfg.get("new", "new_option") == "420"

        options = cfg.options("existing")
        assert len(options) == 2
        assert cfg.get("existing", "new_option") == "142"
        assert cfg.get("existing", "existing_option") == "42"
