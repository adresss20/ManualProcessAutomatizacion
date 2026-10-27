"""
resizer.py
==========
Lógica pura de redimensionado.

Dada una imagen de origen, produce una imagen de exactamente
TARGET_WIDTH x TARGET_HEIGHT sin deformar el producto:

  1. Se corrige la orientación EXIF (fotos tomadas de lado).
  2. Se escala la imagen manteniendo su proporción original para que
     quepa completa dentro del lienzo destino ("contain", no recorta).
  3. Se centra sobre un lienzo del tamaño exacto pedido.
  4. El espacio sobrante se rellena con el color de fondo (blanco).

Este módulo no toca el disco de origen: recibe/entrega objetos Pillow.
"""

from PIL import Image, ImageOps


def resize_with_padding(
    image: Image.Image,
    target_width: int,
    target_height: int,
    background_color=(255, 255, 255),
    padding: int = 0,
) -> Image.Image:
    """Devuelve una nueva imagen RGB de target_width x target_height.

    La imagen original se escala manteniendo su relación de aspecto para
    caber completa (con un margen interior opcional `padding`) y se centra
    sobre un fondo del color indicado.
    """
    # 1. Respetar la orientación registrada en los metadatos EXIF.
    image = ImageOps.exif_transpose(image)

    # 2. Aplanar transparencia (PNG/WebP con alfa) sobre el color de fondo,
    #    de modo que el resultado JPEG no muestre negro donde había alfa.
    if image.mode in ("RGBA", "LA") or (
        image.mode == "P" and "transparency" in image.info
    ):
        base = Image.new("RGB", image.size, background_color)
        rgba = image.convert("RGBA")
        base.paste(rgba, mask=rgba.split()[-1])
        image = base
    else:
        image = image.convert("RGB")

    # 3. Área útil dentro del lienzo (descontando el margen interior).
    inner_w = max(1, target_width - 2 * padding)
    inner_h = max(1, target_height - 2 * padding)

    # 4. Escalar "contain": la imagen completa cabe dentro del área útil.
    src_w, src_h = image.size
    scale = min(inner_w / src_w, inner_h / src_h)
    new_w = max(1, round(src_w * scale))
    new_h = max(1, round(src_h * scale))
    resized = image.resize((new_w, new_h), Image.LANCZOS)

    # 5. Pegar centrado sobre el lienzo destino.
    canvas = Image.new("RGB", (target_width, target_height), background_color)
    offset_x = (target_width - new_w) // 2
    offset_y = (target_height - new_h) // 2
    canvas.paste(resized, (offset_x, offset_y))

    return canvas


def needs_resize(image: Image.Image, target_width: int, target_height: int) -> bool:
    """True si la imagen no tiene ya el tamaño exacto de destino."""
    return image.size != (target_width, target_height)
