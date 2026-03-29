from PySide6.QtCore import QRect
from PySide6.QtGui import QGuiApplication

def logical_to_physical(rect: QRect) -> QRect:
    """Convert a logical QRect into a physical physical QRect for mss capturing."""
    app = QGuiApplication.instance()
    if not app:
        return rect
    
    screen = app.screenAt(rect.topLeft())
    if not screen:
        # Fallback if not cleanly located
        return rect
        
    dpr = screen.devicePixelRatio()
    sx = screen.geometry().x()
    sy = screen.geometry().y()
    px = sx + (rect.x() - sx) * dpr
    py = sy + (rect.y() - sy) * dpr
    return QRect(int(px), int(py), int(rect.width() * dpr), int(rect.height() * dpr))
