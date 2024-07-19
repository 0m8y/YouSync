from PIL import Image, ImageDraw, ImageTk


def add_round_corners(im, rad):
    circle = Image.new('L', (rad * 2, rad * 2), 0)
    draw = ImageDraw.Draw(circle)
    draw.ellipse((0, 0, rad * 2, rad * 2), fill=255)
    alpha = Image.new('L', im.size, 255)
    w, h = im.size
    alpha.paste(circle.crop((0, 0, rad, rad)), (0, 0))
    alpha.paste(circle.crop((0, rad, rad, rad * 2)), (0, h - rad))
    alpha.paste(circle.crop((rad, 0, rad * 2, rad)), (w - rad, 0))
    alpha.paste(circle.crop((rad, rad, rad * 2, rad * 2)), (w - rad, h - rad))
    im.putalpha(alpha)
    return im


def crop_center(img, crop_width, crop_height):
    img_width, img_height = img.size
    start_x = (img_width - crop_width) // 2
    start_y = (img_height - crop_height) // 2
    return img.crop((start_x, start_y, start_x + crop_width, start_y + crop_height))


def create_image(image_path, target_width, target_height):
    img = Image.open(image_path)
    aspect_ratio = img.width / img.height
    new_height = target_height
    new_width = int(new_height * aspect_ratio)
    img = img.resize((new_width, new_height), Image.LANCZOS)
    img = crop_center(img, target_width, target_height)
    img = add_round_corners(img, rad=7)
    return ImageTk.PhotoImage(img)


def truncate_string(s, max_length):
    if s is None:
        return None
    if len(s) > max_length:
        return s[:max_length - 3] + "..."
    return s
