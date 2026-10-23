"""Preserve historical offers before introducing the three size-based tiers."""

from copy import deepcopy
from typing import ClassVar

from django.db import migrations
from django.db.models import Max

# Frozen commercial copy: future defaults must not alter this historical migration.
REQUIREMENT_DEFAULTS = {
    "es": {
        "packagesTitle": "Paquetes de requerimientos por talla",
        "packagesIntro": "Implementa cambios XS, S y M describiendo el resultado esperado y confirmando "
        "su talla antes de programarlos. Elige un paquete con cupos y precio "
        "definidos.",
        "effortBadge": "Cada talla se usa por separado. Los alcances L y XL requieren levantamiento y "
        "cotización independientes. Las correcciones cubiertas por garantía no consumen "
        "cupos.",
        "scopeParagraphs": [
            ("El trabajo aprobado y cotizado corresponde únicamente a lo descrito dentro "
            "del alcance de esta propuesta comercial y de su detalle técnico. Cualquier "
            "conversación, mensaje, correo electrónico, reunión, idea, recurso, "
            "archivo, referencia o solicitud que surja **antes o durante** el proyecto "
            "y que no esté explícitamente descrita dentro de dicho alcance no "
            "constituye, por sí sola, un compromiso de implementación ni hace parte del "
            "trabajo contratado."),
            ("Lo anterior no limita la comunicación: podemos conversar y explorar ideas "
            "libremente. Sin embargo, para que una funcionalidad, cambio o entregable "
            "pase a formar parte del trabajo aprobado, debe quedar documentado y "
            "cotizado como parte del alcance, y formalizarse mediante un otrosí al "
            "contrato o mediante un contrato independiente. Esto protege a ambas "
            "partes: evita malentendidos sobre lo que está incluido, mantiene el "
            "proyecto enfocado y asegura que cada esfuerzo adicional se planifique y se "
            "remunere de forma justa."),
            ("En consecuencia, los tiempos, costos y garantías de esta propuesta aplican "
            "solamente sobre el alcance descrito. Todo lo que lo exceda se gestionará "
            "mediante los paquetes de requerimientos anteriores (tallas XS, S y M) o "
            "como una cotización independiente con levantamiento específico (tallas L y "
            "XL)."),
            ("La ejecución de cualquier actividad no comprendida en el alcance no lo "
            "modifica, no genera derecho a exigir prestaciones similares en el futuro "
            "ni implica renuncia a lo aquí establecido."),
        ],
    },
    "en": {
        "packagesTitle": "Requirement packages by size",
        "packagesIntro": "Implement XS, S and M changes by agreeing on the expected result and "
        "confirming their size before scheduling. Choose a package with defined "
        "allowances and pricing.",
        "effortBadge": "Allowances cannot be exchanged between sizes. L and XL require separate "
        "discovery and a quote. Warranty corrections do not use allowances.",
        "scopeParagraphs": [
            ("The approved and quoted work corresponds solely to what is described "
            "within the scope of this commercial proposal and its technical detail. Any "
            "conversation, message, email, meeting, idea, resource, file, reference or "
            "request that arises **before or during** the project and is not explicitly "
            "described within that scope does not, by itself, constitute a commitment "
            "to implement it, nor is it part of the contracted work."),
            ("This does not limit communication: we can talk and explore ideas freely. "
            "However, for a feature, change or deliverable to become part of the "
            "approved work, it must be documented and quoted as part of the scope, and "
            "formalized through an amendment to the contract or through an independent "
            "contract. This protects both parties: it avoids misunderstandings about "
            "what is included, keeps the project focused, and ensures every additional "
            "effort is planned and fairly paid."),
            ("Consequently, the timelines, costs and warranties of this proposal apply "
            "only to the described scope. Anything beyond it will use the requirement "
            "packages above (XS, S, M), or separate discovery and a quote (L and XL)."),
            ("Carrying out any activity outside the scope does not modify it, does not "
            "create a right to demand similar work in the future, and does not waive "
            "anything stated here."),
        ],
    },
}


def seed(apps, schema_editor):
    Package = apps.get_model("content", "HourPackage")
    Section = apps.get_model("content", "ProposalSection")
    # Capture the effective old automatic catalog, not an invented hours→sizes conversion.
    for section in (
        Section.objects.filter(section_type="commercial_conditions")
        .select_related("proposal")
        .iterator()
    ):
        data = deepcopy(section.content_json or {})
        if data.get("pricingModel") == "requirements":
            continue
        proposal = section.proposal
        rows = list(
            Package.objects.filter(
                nationality=proposal.nationality, is_active=True, pricing_model="hours"
            ).order_by("order", "hours")
        )
        if data.get("hourPackagesMode") != "manual" and rows:
            en = proposal.language == "en"
            data["packages"] = [
                {
                    "id": p.pk,
                    "name": p.name_en if en else p.name_es,
                    "note": p.note_en if en else p.note_es,
                    "hours": p.hours,
                    "hourlyRate": float(p.hourly_rate),
                    "discountPercent": p.discount_percent,
                }
                for p in rows
            ]
        data["pricingModel"] = "hours"
        data["packagesFrozen"] = True
        Section.objects.filter(pk=section.pk).update(content_json=data)
    Package.objects.filter(pricing_model="hours").update(is_active=False)
    tiers = [
        ("Paquete Ágil", "Agile Pack", 30, 0, 0, 10),
        ("Paquete Pro", "Pro Pack", 30, 20, 0, 15),
        ("Paquete Premium", "Premium Pack", 30, 20, 10, 25),
    ]
    for nationality in ("COL", "EXT", "USA"):
        for order, (es, en, xs, small, medium, discount) in enumerate(tiers, 1):
            Package.objects.create(
                nationality=nationality,
                pricing_model="requirements",
                name_es=es,
                name_en=en,
                xs_count=xs,
                s_count=small,
                m_count=medium,
                discount_percent=discount,
                order=order,
                validity_months=12,
                is_active=True,
            )

    # Saved defaults take priority over code defaults for every new proposal.
    # Update only future commercial content; the old offers above stay frozen.
    DefaultConfig = apps.get_model("content", "ProposalDefaultConfig")
    for config in DefaultConfig.objects.all():
        changed = False
        sections = deepcopy(config.sections_json or [])
        for section in sections:
            if (
                not isinstance(section, dict)
                or section.get("section_type") != "commercial_conditions"
            ):
                continue
            content = section.get("content_json") or {}
            if content.get("pricingModel") == "requirements":
                continue
            content = deepcopy(content)
            content.update(
                deepcopy(
                    REQUIREMENT_DEFAULTS.get(
                        config.language, REQUIREMENT_DEFAULTS["es"]
                    )
                )
            )
            content.update(
                pricingModel="requirements",
                hourPackagesMode="auto",
                packagesFrozen=False,
                packages=[],
            )
            for key in (
                "hourlyRate",
                "manualHourlyRate",
                "manualPackageRates",
                "manualCurrency",
            ):
                content.pop(key, None)
            section["content_json"] = content
            changed = True
        if changed:
            config.sections_json = sections
            config.save(update_fields=["sections_json"])

    Connector = apps.get_model("content", "McpConnector")
    for connector in Connector.objects.filter(description__icontains="paquetes de horas"):
        connector.description = connector.description.replace(
            "paquetes de horas", "paquetes de requerimientos"
        ).replace("Paquetes de horas", "Paquetes de requerimientos")
        connector.save(update_fields=["description"])

    Template = apps.get_model("content", "ContractTemplate")
    Version = apps.get_model("content", "ContractTemplateVersion")
    for template in Template.objects.all():
        for variant, field in [
            ("combined", "content_markdown"),
            ("product", "product_content_markdown"),
            ("service", "service_content_markdown"),
        ]:
            old = getattr(template, field) or ""
            new = old.replace(
                "paquetes de horas", "paquetes de requerimientos XS, S y M"
            )
            new = new.replace("esfuerzos bajos o medio-bajos", "tallas XS, S o M")
            new = new.replace(
                "esfuerzos medios o superiores",
                "tallas L o XL, con levantamiento específico",
            )
            if new != old:
                Template.objects.filter(pk=template.pk).update(**{field: new})
                last = (
                    Version.objects.filter(
                        template=template, variant=variant
                    ).aggregate(n=Max("version"))["n"]
                    or 0
                )
                revision = Version.objects.create(
                    template=template,
                    variant=variant,
                    version=last + 1,
                    markdown=new,
                    author_label="Sistema",
                    change_note="Paquetes por talla: XS/S/M; L/XL requieren levantamiento independiente.",
                )
                # The live mirror is a current draft, not a historical signed file.
                Mirror = apps.get_model("content", "ContractTemplateMirror")
                if Mirror.objects.filter(template=template, variant=variant).exists():
                    from django.utils import timezone

                    from content.services.contract_mirror_service import (
                        render_mirror_pdf,
                    )

                    setattr(template, field, new)
                    pdf = render_mirror_pdf(template, variant)
                    if not pdf or not pdf.startswith(b"%PDF-"):
                        raise ValueError(
                            "No se pudo sincronizar el espejo contractual por talla."
                        )
                    Mirror.objects.filter(template=template, variant=variant).update(
                        revision=revision, pdf_content=pdf, synced_at=timezone.now()
                    )


class Migration(migrations.Migration):
    dependencies: ClassVar[list] = [("content", "0301_requirement_packages")]
    # Reversing must never re-activate superseded commercial commitments.
    operations: ClassVar[list] = [migrations.RunPython(seed, migrations.RunPython.noop)]
