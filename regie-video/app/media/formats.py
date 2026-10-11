"""Formats de fichiers acceptés."""

VIDEO_EXTENSIONS = (".mp4", ".m4v", ".mov", ".mkv", ".avi", ".wmv", ".webm")
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp", ".webp")

VIDEO_FILTER = "Vidéos (" + " ".join(f"*{e}" for e in VIDEO_EXTENSIONS) + ")"
IMAGE_FILTER = "Images (" + " ".join(f"*{e}" for e in IMAGE_EXTENSIONS) + ")"
