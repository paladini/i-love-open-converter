# Request: blur faces in images

## Source request

The image catalog describes this tool as: “Desfocar cara. Desfoque facilmente caras e placas. Você também pode desfocar objetos para esconder informação privada.”

## Outcome

Activate the existing `Desfocar cara` tool. Let a visitor submit one supported static image; detect frontal or profile faces locally and apply strong Gaussian blur to the detected regions; return one image in PNG, JPEG, or WebP.

The first version is deliberately face-only and uses OpenCV's built-in Haar cascade classifiers on the self-hosted server. It does not detect license plates or arbitrary objects, guarantee every face is detected, or replace a careful privacy review of the output. If no face is detected, fail with a clear message and do not offer the unchanged image as a successful privacy result.
