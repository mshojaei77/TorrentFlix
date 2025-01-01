def format_movie_title(title):
    return title.title()

def safe_filename(name):
    return "".join(c for c in name if c.isalnum() or c in (' ', '_')).rstrip()