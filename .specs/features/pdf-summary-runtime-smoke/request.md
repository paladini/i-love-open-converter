# Request

"É pra seguir, e ir criando PRs de tudo, mergeando, até finalizar completamente a implementação do nosso plano original!"

## Work

Close the remaining runtime verification gap from `.specs/features/pdf-abstractive-summary/review.md`: exercise the bundled local summary model through the final Python 3.14 runtime during the Docker build. Fail the image build if local model loading or inference does not produce text. Block network connections during this check. This is build-time verification only and must not change the application flow.

**Review:** sent at 270fe42
**Fix pass:** done - The summary inference step now runs in a separate Docker `RUN --network=none` instruction.
**CI follow-up review:** sent at 35d5e18

## CI follow-up

The pull request container check must complete in a practical time while still building the final runtime and running the offline summary inference smoke check. Pull request CI builds `linux/amd64`; pushes to `main` and the image publishing workflow continue to build both `linux/amd64` and `linux/arm64`. This changes validation coverage by event only and does not change the supported image architectures or application behavior.
