"""
Routes API pour l'export de données.
"""
import csv
import io
from datetime import datetime

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from ...core.database import get_active_session, get_db

router = APIRouter()


@router.get("/csv")
async def export_csv():
    """Exporte les métriques de la session active en CSV."""
    session = get_active_session()
    if not session:
        return {"error": "Aucune session active"}
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT timestamp, estimated_tokens, percentage, content_preview, 
                      prompt_tokens, completion_tokens, is_estimated, source
               FROM metrics 
               WHERE session_id = ? 
               ORDER BY timestamp DESC""",
            (session["id"],)
        )
        rows = cursor.fetchall()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Timestamp", "Tokens Total", "Pourcentage", "Aperçu", 
                     "Prompt Tokens", "Completion Tokens", "Type", "Source"])
    
    for row in rows:
        writer.writerow([
            row[0],
            row[1],
            f"{row[2]:.2f}%",
            row[3],
            row[4] or 0,
            row[5] or 0,
            "Estimé" if row[6] else "Réel",
            row[7] or "proxy"
        ])
    
    output.seek(0)
    filename = f"session_{session['id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8')),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/json")
async def export_json():
    """Exporte les métriques de la session active en JSON."""
    session = get_active_session()
    if not session:
        return {"error": "Aucune session active"}
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT * FROM metrics WHERE session_id = ? ORDER BY timestamp DESC""",
            (session["id"],)
        )
        metrics = [dict(row) for row in cursor.fetchall()]
    
    return {
        "session": session,
        "metrics": metrics,
        "exported_at": datetime.now().isoformat()
    }
