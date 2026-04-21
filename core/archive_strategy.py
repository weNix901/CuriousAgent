"""Archive strategy for cold knowledge (v0.3.3)."""
import gzip
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)


class ArchiveStrategy:
    """Archive cold knowledge nodes to save disk space."""
    
    def __init__(
        self,
        cold_threshold: int = 30,
        delete_txt: bool = True,
        compress_pdf: bool = True,
        keep_metadata: bool = True
    ):
        self.cold_threshold = cold_threshold
        self.delete_txt = delete_txt
        self.compress_pdf = compress_pdf
        self.keep_metadata = keep_metadata
    
    def should_archive(self, heat: float) -> bool:
        """Check if node should be archived."""
        return heat < self.cold_threshold
    
    def archive_node(self, node: dict) -> dict:
        """Archive a cold knowledge node."""
        heat = node.get("heat", 100)
        if not self.should_archive(heat):
            return node
        
        # Skip derived nodes (child knowledge points)
        if node.get("source_origin_type") == "derived":
            return node
        
        now = datetime.now().isoformat()
        
        # Delete TXT file (processing layer, can be regenerated)
        txt_path = node.get("txt_path")
        if self.delete_txt and txt_path and os.path.exists(txt_path):
            os.remove(txt_path)
            node["txt_path"] = None
            node["txt_archived_at"] = now
            logger.info(f"Archived TXT: {txt_path}")
        
        # Compress PDF (don't delete, reduce disk usage)
        pdf_path = node.get("pdf_path")
        if self.compress_pdf and pdf_path and os.path.exists(pdf_path):
            gz_path = pdf_path + ".gz"
            if not os.path.exists(gz_path):
                with open(pdf_path, "rb") as f_in:
                    with gzip.open(gz_path, "wb") as f_out:
                        f_out.write(f_in.read())
                os.remove(pdf_path)
                node["pdf_path"] = gz_path
                node["pdf_compressed_at"] = now
                logger.info(f"Compressed PDF: {pdf_path} → {gz_path}")
        
        node["archive_status"] = "archived"
        node["archive_date"] = now
        
        return node
    
    def restore_node(self, node: dict) -> dict:
        """Restore an archived node (decompress PDF)."""
        pdf_path = node.get("pdf_path")
        if pdf_path and pdf_path.endswith(".gz") and os.path.exists(pdf_path):
            original_path = pdf_path[:-3]  # Remove .gz
            with gzip.open(pdf_path, "rb") as f_in:
                with open(original_path, "wb") as f_out:
                    f_out.write(f_in.read())
            node["pdf_path"] = original_path
            node["archive_status"] = "restored"
            logger.info(f"Restored PDF: {pdf_path} → {original_path}")
        
        return node