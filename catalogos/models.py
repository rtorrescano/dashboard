# catalogos/models.py
from django.db import models
from django.db.models import Q


class CatalogoGeografico(models.Model):
    """
    Catálogo geográfico del INEGI (entidades y municipios).
    Se puebla con el catálogo oficial antes de correr los ETL.
    - cve_mun IS NULL  -> registro a nivel entidad
    - cve_mun NOT NULL -> registro a nivel municipio
    """
    cve_ent = models.CharField(max_length=2, db_index=True)
    nom_ent = models.CharField(max_length=200, db_index=True)
    cve_mun = models.CharField(max_length=3, null=True, blank=True, db_index=True)
    nom_mun = models.CharField(max_length=200, null=True, blank=True)

    class Meta:
        db_table = 'catalogo_geografico'
        constraints = [
            models.UniqueConstraint(
                fields=['cve_ent', 'cve_mun'],
                condition=Q(cve_mun__isnull=False),
                name='unique_cat_geo_ent_mun',
            ),
            models.UniqueConstraint(
                fields=['cve_ent'],
                condition=Q(cve_mun__isnull=True),
                name='unique_cat_geo_ent_only',
            ),
        ]
        indexes = [
            models.Index(fields=['nom_ent']),
            models.Index(fields=['nom_mun']),
        ]

    def __str__(self):
        base = f"{self.cve_ent} - {self.nom_ent}"
        if self.cve_mun:
            base += f" / {self.cve_mun} - {self.nom_mun}"
        return base