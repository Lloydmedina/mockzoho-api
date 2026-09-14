"""Single source of truth for the mocked Zoho CRM modules.

Field names are inferred from the repair-domain tickets plus standard Zoho CRM
fields. When the real `BaseCRMAdapter` contract is known, correct the specs here
and every route, validator, seed loader and COQL query follows automatically.
"""

from dataclasses import dataclass, field
from typing import Any, Literal

FieldType = Literal[
    "string",
    "text",
    "integer",
    "double",
    "boolean",
    "datetime",
    "date",
    "picklist",
    "email",
    "phone",
    "lookup",
]


@dataclass(frozen=True)
class FieldSpec:
    api_name: str
    type: FieldType = "string"
    required: bool = False
    picklist_values: tuple[str, ...] = ()
    lookup_module: str | None = None
    read_only: bool = False


@dataclass(frozen=True)
class ModuleSpec:
    api_name: str
    singular: str
    plural: str
    fields: tuple[FieldSpec, ...]
    related_lists: dict[str, tuple[str, str]] = field(default_factory=dict)
    """related_list_name -> (target_module, lookup_field_on_target)"""

    def field_map(self) -> dict[str, FieldSpec]:
        return {f.api_name: f for f in self.fields}

    def required_fields(self) -> tuple[FieldSpec, ...]:
        return tuple(f for f in self.fields if f.required)


SYSTEM_FIELDS: tuple[str, ...] = (
    "id",
    "Created_Time",
    "Modified_Time",
    "Created_By",
    "Modified_By",
    "Owner",
    "$approval",
    "$process_flow",
)

CASES = ModuleSpec(
    api_name="Cases",
    singular="Case",
    plural="Cases",
    fields=(
        FieldSpec("Subject", "string", required=True),
        FieldSpec("Case_Number", "string"),
        FieldSpec(
            "Status",
            "picklist",
            picklist_values=("Open", "In Progress", "Waiting for Parts", "Escalated", "Closed"),
        ),
        FieldSpec("Priority", "picklist", picklist_values=("Low", "Medium", "High", "Critical")),
        FieldSpec("Case_Origin", "picklist", picklist_values=("Phone", "Email", "Web", "Field")),
        FieldSpec("Case_Type", "picklist", picklist_values=("Repair", "Installation", "Maintenance", "Inspection")),
        FieldSpec("Description", "text"),
        FieldSpec("Resolution", "text"),
        FieldSpec("Product", "lookup", lookup_module="Products"),
        FieldSpec("Serial_Number", "string"),
        FieldSpec("Customer_Name", "string"),
        FieldSpec("Phone", "phone"),
        FieldSpec("Email", "email"),
        FieldSpec("Service_Address", "text"),
        FieldSpec("City", "string"),
        FieldSpec("Technician", "string"),
        FieldSpec(
            "Warranty_Status",
            "picklist",
            picklist_values=("In Warranty", "Out of Warranty", "Extended", "Unknown"),
        ),
        FieldSpec("Reported_Date", "datetime"),
        FieldSpec("Closed_Date", "datetime"),
        FieldSpec("Total_Labor_Cost", "double"),
        FieldSpec("Total_Parts_Cost", "double"),
    ),
    related_lists={
        "Visits": ("Visits", "Case"),
        "Labor_Costs": ("Labor_Costs", "Case"),
        "Spare_Parts": ("Spare_Parts", "Case"),
        "Case_Actions": ("Case_Actions", "Case"),
    },
)

VISITS = ModuleSpec(
    api_name="Visits",
    singular="Visit",
    plural="Visits",
    fields=(
        FieldSpec("Name", "string", required=True),
        FieldSpec("Case", "lookup", required=True, lookup_module="Cases"),
        FieldSpec("Visit_Date", "datetime"),
        FieldSpec(
            "Status",
            "picklist",
            picklist_values=("Scheduled", "En Route", "In Progress", "Completed", "Cancelled", "No Show"),
        ),
        FieldSpec("Visit_Type", "picklist", picklist_values=("Diagnostic", "Repair", "Follow Up", "Installation")),
        FieldSpec("Technician", "string"),
        FieldSpec("Technician_Id", "string"),
        FieldSpec("Duration_Minutes", "integer"),
        FieldSpec("Arrival_Time", "datetime"),
        FieldSpec("Departure_Time", "datetime"),
        FieldSpec("Customer_Signature", "string"),
        FieldSpec("Notes", "text"),
    ),
    related_lists={
        "Labor_Costs": ("Labor_Costs", "Visit"),
        "Spare_Parts": ("Spare_Parts", "Visit"),
        "Case_Actions": ("Case_Actions", "Visit"),
    },
)

PRODUCTS = ModuleSpec(
    api_name="Products",
    singular="Product",
    plural="Products",
    fields=(
        FieldSpec("Product_Name", "string", required=True),
        FieldSpec("Product_Code", "string"),
        FieldSpec("Product_Category", "picklist", picklist_values=("Air Conditioner", "Heat Pump", "Boiler", "Spare Part", "Accessory")),
        FieldSpec("Manufacturer", "string"),
        FieldSpec("Model_Number", "string"),
        FieldSpec("Unit_Price", "double"),
        FieldSpec("Qty_in_Stock", "integer"),
        FieldSpec("Warranty_Months", "integer"),
        FieldSpec("Product_Active", "boolean"),
        FieldSpec("Description", "text"),
    ),
)

LABOR_COSTS = ModuleSpec(
    api_name="Labor_Costs",
    singular="Labor_Cost",
    plural="Labor_Costs",
    fields=(
        FieldSpec("Name", "string", required=True),
        FieldSpec("Case", "lookup", required=True, lookup_module="Cases"),
        FieldSpec("Visit", "lookup", lookup_module="Visits"),
        FieldSpec("Work_Type", "picklist", picklist_values=("Diagnostic", "Repair", "Installation", "Travel", "Overtime")),
        FieldSpec("Technician", "string"),
        FieldSpec("Hours", "double"),
        FieldSpec("Hourly_Rate", "double"),
        FieldSpec("Total_Cost", "double"),
        FieldSpec("Currency", "string"),
        FieldSpec("Billable", "boolean"),
        FieldSpec("Work_Date", "date"),
        FieldSpec("Notes", "text"),
    ),
)

SPARE_PARTS = ModuleSpec(
    api_name="Spare_Parts",
    singular="Spare_Part",
    plural="Spare_Parts",
    fields=(
        FieldSpec("Name", "string", required=True),
        FieldSpec("Case", "lookup", required=True, lookup_module="Cases"),
        FieldSpec("Visit", "lookup", lookup_module="Visits"),
        FieldSpec("Product", "lookup", lookup_module="Products"),
        FieldSpec("Part_Code", "string"),
        FieldSpec("Quantity", "integer"),
        FieldSpec("Unit_Price", "double"),
        FieldSpec("Total_Cost", "double"),
        FieldSpec("Warranty_Covered", "boolean"),
        FieldSpec(
            "Status",
            "picklist",
            picklist_values=("Requested", "Ordered", "In Transit", "Delivered", "Installed", "Returned"),
        ),
        FieldSpec("Notes", "text"),
    ),
)

CASE_ACTIONS = ModuleSpec(
    api_name="Case_Actions",
    singular="Case_Action",
    plural="Case_Actions",
    fields=(
        FieldSpec("Name", "string", required=True),
        FieldSpec("Case", "lookup", required=True, lookup_module="Cases"),
        FieldSpec("Visit", "lookup", lookup_module="Visits"),
        FieldSpec(
            "Action_Type",
            "picklist",
            picklist_values=(
                "Case Created",
                "Assigned",
                "Diagnosed",
                "Part Ordered",
                "Repaired",
                "Escalated",
                "Customer Contacted",
                "Closed",
            ),
        ),
        FieldSpec("Action_Date", "datetime"),
        FieldSpec("Performed_By", "string"),
        FieldSpec("Result", "picklist", picklist_values=("Success", "Failed", "Pending", "Deferred")),
        FieldSpec("Comments", "text"),
    ),
)

MODULES: dict[str, ModuleSpec] = {
    m.api_name: m
    for m in (CASES, VISITS, PRODUCTS, LABOR_COSTS, SPARE_PARTS, CASE_ACTIONS)
}

MODULE_NAMES: tuple[str, ...] = tuple(MODULES)

_LOOKUP_BY_LOWER = {name.lower(): name for name in MODULES}


def resolve_module(name: str) -> ModuleSpec | None:
    """Case-insensitive module resolution; returns None for unknown modules."""
    canonical = _LOOKUP_BY_LOWER.get((name or "").lower())
    return MODULES[canonical] if canonical else None


def is_system_field(name: str) -> bool:
    return name in SYSTEM_FIELDS


def module_summary() -> dict[str, Any]:
    return {
        name: {
            "fields": [f.api_name for f in spec.fields],
            "required": [f.api_name for f in spec.required_fields()],
            "related_lists": list(spec.related_lists),
        }
        for name, spec in MODULES.items()
    }
