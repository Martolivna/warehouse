# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

from sqlalchemy.sql.expression import func, literal

from warehouse.oidc.models import GitHubProvider, PendingGitHubProvider

GITHUB_OIDC_ISSUER_URL = "https://token.actions.githubusercontent.com"

OIDC_ISSUER_URLS = {GITHUB_OIDC_ISSUER_URL}


def find_provider_by_issuer(session, issuer_url, signed_claims, *, pending=False):
    """
    Given an OIDC issuer URL and a dictionary of claims that have been verified
    for a token from that OIDC issuer, retrieve either an `OIDCProvider` registered
    to one or more projects or a `PendingOIDCProvider`, varying with the
    `pending` parameter.

    Returns `None` if no provider can be found.
    """

    if issuer_url not in OIDC_ISSUER_URLS:
        # This indicates a logic error, since we shouldn't have verified
        # claims for an issuer that we don't recognize and support.
        return None

    # This is the ugly part: OIDCProvider and PendingOIDCProvider are both
    # polymorphic, and retrieving the correct provider requires us to query
    # based on provider-specific claims.
    if issuer_url == GITHUB_OIDC_ISSUER_URL:
        repository = signed_claims["repository"]
        repository_owner, repository_name = repository.split("/", 1)
        workflow_prefix = f"{repository}/.github/workflows/"
        workflow_ref = signed_claims["job_workflow_ref"].removeprefix(workflow_prefix)

        provider_cls = GitHubProvider if not pending else PendingGitHubProvider

        return (
            session.query(provider_cls)
            .filter_by(
                repository_name=repository_name,
                repository_owner=repository_owner,
                repository_owner_id=signed_claims["repository_owner_id"],
            )
            .filter(
                literal(workflow_ref).like(
                    func.concat(provider_cls.workflow_filename, "%")
                )
            )
            .one_or_none()
        )
    else:
        # Unreachable; same logic error as above.
        return None  # pragma: no cover
