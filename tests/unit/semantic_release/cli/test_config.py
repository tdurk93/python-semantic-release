from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import mock

import pytest
import tomlkit
from pydantic import ValidationError

from semantic_release.cli.config import (
    EnvConfigVar,
    GlobalCommandLineOptions,
    HvcsClient,
    RawConfig,
    RuntimeContext,
)
from semantic_release.const import DEFAULT_COMMIT_AUTHOR

if TYPE_CHECKING:
    from typing import Any


@pytest.mark.parametrize(
    "remote_config, expected_token",
    [
        ({"type": HvcsClient.GITHUB.value}, EnvConfigVar(env="GH_TOKEN")),
        ({"type": HvcsClient.GITLAB.value}, EnvConfigVar(env="GITLAB_TOKEN")),
        ({"type": HvcsClient.GITEA.value}, EnvConfigVar(env="GITEA_TOKEN")),
        ({}, EnvConfigVar(env="GH_TOKEN")),  # default not provided -> means Github
    ],
)
def test_load_hvcs_default_token(remote_config: dict[str, Any], expected_token):
    raw_config = RawConfig.model_validate(
        {
            "remote": remote_config,
        }
    )
    assert expected_token == raw_config.remote.token


@pytest.mark.parametrize("remote_config", [{"type": "nonexistent"}])
def test_invalid_hvcs_type(remote_config: dict[str, Any]):
    with pytest.raises(ValidationError) as excinfo:
        RawConfig.model_validate(
            {
                "remote": remote_config,
            }
        )
    assert "remote.type" in str(excinfo.value)


def test_default_toml_config_valid(example_project):
    default_config_file = example_project / "default.toml"
    default_config_file.write_text(
        tomlkit.dumps(RawConfig().model_dump(mode="json", exclude_none=True))
    )

    written = default_config_file.read_text(encoding="utf-8")
    loaded = tomlkit.loads(written).unwrap()
    # Check that we can load it correctly
    parsed = RawConfig.model_validate(loaded)
    assert parsed
    # Check the re-loaded internal representation is sufficient
    # There is an issue with BaseModel.__eq__ that means
    # comparing directly doesn't work with parsed.dict(); this
    # is because of how tomlkit parsed toml


@pytest.mark.parametrize(
    "mock_env, expected_author",
    [
        ({}, DEFAULT_COMMIT_AUTHOR),
        ({"GIT_COMMIT_AUTHOR": "foo <foo>"}, "foo <foo>"),
    ],
)
def test_commit_author_configurable(
    example_project, repo_with_no_tags_angular_commits, mock_env, expected_author
):
    pyproject_toml = example_project / "pyproject.toml"
    content = tomlkit.loads(pyproject_toml.read_text(encoding="utf-8")).unwrap()

    with mock.patch.dict("os.environ", mock_env):
        raw = RawConfig.model_validate(content)
        runtime = RuntimeContext.from_raw_config(
            raw=raw,
            repo=repo_with_no_tags_angular_commits,
            global_cli_options=GlobalCommandLineOptions(),
        )
        assert (
            f"{runtime.commit_author.name} <{runtime.commit_author.email}>"
            == expected_author
        )
