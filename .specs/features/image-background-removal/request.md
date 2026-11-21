# Request: remove image backgrounds

## Source request

The image catalog describes this tool as: “Remova rapidamente fundos de imagens com alta precisão. Detecte instantâneamente objetos e corte o fundo com facilidade.”

## Outcome

Activate the existing “Remover fundo” image tool. Let a visitor submit one supported static image and download a PNG cutout with a transparent background. All image inference runs on the self-hosted server with a locally installed lightweight model; image bytes are not sent to a cloud service.

The first version uses the U2NetP general salient-object model through rembg's CPU runtime. It does not promise perfect edges or support user-drawn masks, batch jobs, alternate backgrounds, or cloud inference. The model weights and their separate license must be disclosed and attributed.
