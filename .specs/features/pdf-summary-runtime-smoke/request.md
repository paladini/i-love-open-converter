# Request

"É pra seguir, e ir criando PRs de tudo, mergeando, até finalizar completamente a implementação do nosso plano original!"

## Work

Close the remaining runtime verification gap from `.specs/features/pdf-abstractive-summary/review.md`: exercise the bundled local summary model through the final Python 3.14 runtime during the Docker build. Fail the image build if local model loading or inference does not produce text. Block network connections during this check. This is build-time verification only and must not change the application flow.

**Review:** sent at 270fe42
**Fix pass:** done - The summary inference step now runs in a separate Docker `RUN --network=none` instruction.
