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

LEADS = ModuleSpec(
    api_name="Leads",
    singular="Lead",
    plural="Leads",
    fields=(
        FieldSpec("Last_Name", "string", required=True),
        FieldSpec("First_Name", "string"),
        FieldSpec("Company", "string"),
        FieldSpec("Email", "email"),
        FieldSpec("Phone", "phone"),
        FieldSpec("Mobile", "phone"),
        FieldSpec(
            "Lead_Source",
            "picklist",
            picklist_values=(
                "Advertisement",
                "Cold Call",
                "Employee Referral",
                "External Referral",
                "Online Store",
                "Partner",
                "Public Relations",
                "Trade Show",
                "Web Download",
                "Web Research",
                "Chat",
            ),
        ),
        FieldSpec(
            "Lead_Status",
            "picklist",
            picklist_values=("Contacted", "Not Contacted", "Qualified", "Junk Lead", "Lost Lead"),
        ),
        FieldSpec("Rating", "picklist", picklist_values=("Hot", "Warm", "Cold")),
        FieldSpec(
            "Industry",
            "picklist",
            picklist_values=("Technology", "Finance", "Healthcare", "Manufacturing", "Retail", "Education", "Other"),
        ),
        FieldSpec("Annual_Revenue", "double"),
        FieldSpec("Description", "text"),
    ),
    related_lists={
        "Tasks": ("Tasks", "Who_Id"),
        "Calls": ("Calls", "Who_Id"),
        "Meetings": ("Meetings", "Who_Id"),
    },
)

CONTACTS = ModuleSpec(
    api_name="Contacts",
    singular="Contact",
    plural="Contacts",
    fields=(
        FieldSpec("Last_Name", "string", required=True),
        FieldSpec("First_Name", "string"),
        FieldSpec("Email", "email"),
        FieldSpec("Phone", "phone"),
        FieldSpec("Mobile", "phone"),
        FieldSpec("Title", "string"),
        FieldSpec("Department", "string"),
        FieldSpec("Account_Name", "lookup", lookup_module="Accounts"),
        FieldSpec("Mailing_City", "string"),
        FieldSpec("Mailing_State", "string"),
        FieldSpec("Mailing_Country", "string"),
        FieldSpec("Description", "text"),
    ),
    related_lists={
        "Tasks": ("Tasks", "Who_Id"),
        "Calls": ("Calls", "Who_Id"),
        "Meetings": ("Meetings", "Who_Id"),
    },
)

ACCOUNTS = ModuleSpec(
    api_name="Accounts",
    singular="Account",
    plural="Accounts",
    fields=(
        FieldSpec("Account_Name", "string", required=True),
        FieldSpec("Phone", "phone"),
        FieldSpec("Website", "string"),
        FieldSpec("Fax", "string"),
        FieldSpec("Billing_City", "string"),
        FieldSpec("Billing_State", "string"),
        FieldSpec("Billing_Country", "string"),
        FieldSpec("Shipping_City", "string"),
        FieldSpec("Shipping_State", "string"),
        FieldSpec("Shipping_Country", "string"),
        FieldSpec(
            "Industry",
            "picklist",
            picklist_values=("Technology", "Finance", "Healthcare", "Manufacturing", "Retail", "Education", "Other"),
        ),
        FieldSpec("Annual_Revenue", "double"),
        FieldSpec("Employees", "integer"),
        FieldSpec("Description", "text"),
    ),
    related_lists={
        "Contacts": ("Contacts", "Account_Name"),
        "Deals": ("Deals", "Account_Name"),
        "Cases": ("Cases", "Account_Name"),
    },
)

DEALS = ModuleSpec(
    api_name="Deals",
    singular="Deal",
    plural="Deals",
    fields=(
        FieldSpec("Deal_Name", "string", required=True),
        FieldSpec("Amount", "double"),
        FieldSpec(
            "Stage",
            "picklist",
            picklist_values=(
                "Qualification",
                "Needs Analysis",
                "Proposal/Price Quote",
                "Negotiation/Review",
                "Closed Won",
                "Closed Lost",
                "Id. Decision Makers",
            ),
        ),
        FieldSpec("Probability", "double"),
        FieldSpec("Closing_Date", "date"),
        FieldSpec("Account_Name", "lookup", lookup_module="Accounts"),
        FieldSpec("Contact_Name", "lookup", lookup_module="Contacts"),
        FieldSpec("Type", "picklist", picklist_values=("New Business", "Existing Business")),
        FieldSpec(
            "Lead_Source",
            "picklist",
            picklist_values=(
                "Advertisement",
                "Cold Call",
                "Employee Referral",
                "External Referral",
                "Online Store",
                "Partner",
                "Public Relations",
                "Trade Show",
                "Web Download",
                "Web Research",
                "Chat",
            ),
        ),
        FieldSpec("Description", "text"),
    ),
    related_lists={
        "Tasks": ("Tasks", "What_Id"),
        "Calls": ("Calls", "What_Id"),
        "Meetings": ("Meetings", "What_Id"),
    },
)

TASKS = ModuleSpec(
    api_name="Tasks",
    singular="Task",
    plural="Tasks",
    fields=(
        FieldSpec("Subject", "string", required=True),
        FieldSpec("Due_Date", "date"),
        FieldSpec(
            "Status",
            "picklist",
            picklist_values=("Not Started", "In Progress", "Completed", "Waiting on someone else", "Deferred"),
        ),
        FieldSpec("Priority", "picklist", picklist_values=("High", "Highest", "Normal", "Lowest", "Low")),
        FieldSpec("What_Id", "lookup", lookup_module="Deals"),
        FieldSpec("Who_Id", "lookup", lookup_module="Contacts"),
        FieldSpec("Description", "text"),
    ),
)

MEETINGS = ModuleSpec(
    api_name="Meetings",
    singular="Meeting",
    plural="Meetings",
    fields=(
        FieldSpec("Subject", "string", required=True),
        FieldSpec("Start_DateTime", "datetime"),
        FieldSpec("End_DateTime", "datetime"),
        FieldSpec("Status", "picklist", picklist_values=("Planned", "Held", "Not Held")),
        FieldSpec("Location", "string"),
        FieldSpec("What_Id", "lookup", lookup_module="Deals"),
        FieldSpec("Who_Id", "lookup", lookup_module="Contacts"),
        FieldSpec("Description", "text"),
    ),
)

CALLS = ModuleSpec(
    api_name="Calls",
    singular="Call",
    plural="Calls",
    fields=(
        FieldSpec("Subject", "string", required=True),
        FieldSpec("Call_Start_Time", "datetime"),
        FieldSpec("Call_Duration", "string"),
        FieldSpec("Call_Type", "picklist", picklist_values=("Inbound", "Outbound")),
        FieldSpec("Call_Result", "picklist", picklist_values=("Attended", "Missed", "Dropped", "Voicemail")),
        FieldSpec("What_Id", "lookup", lookup_module="Deals"),
        FieldSpec("Who_Id", "lookup", lookup_module="Contacts"),
        FieldSpec("Description", "text"),
    ),
)

QUOTES = ModuleSpec(
    api_name="Quotes",
    singular="Quote",
    plural="Quotes",
    fields=(
        FieldSpec("Subject", "string", required=True),
        FieldSpec("Quote_Stage", "picklist", picklist_values=("Draft", "Delivered", "Negotiation", "Closed Won", "Closed Lost")),
        FieldSpec("Valid_Till", "date"),
        FieldSpec("Account_Name", "lookup", lookup_module="Accounts"),
        FieldSpec("Deal_Name", "lookup", lookup_module="Deals"),
        FieldSpec("Grand_Total", "double"),
        FieldSpec("Description", "text"),
    ),
)

SALES_ORDERS = ModuleSpec(
    api_name="Sales_Orders",
    singular="Sales_Order",
    plural="Sales_Orders",
    fields=(
        FieldSpec("Subject", "string", required=True),
        FieldSpec("SO_Number", "string"),
        FieldSpec("Status", "picklist", picklist_values=("Draft", "Pending", "In Progress", "Delivered", "Cancelled")),
        FieldSpec("Account_Name", "lookup", lookup_module="Accounts"),
        FieldSpec("Deal_Name", "lookup", lookup_module="Deals"),
        FieldSpec("Grand_Total", "double"),
        FieldSpec("Pending", "double"),
        FieldSpec("Description", "text"),
    ),
)

PURCHASE_ORDERS = ModuleSpec(
    api_name="Purchase_Orders",
    singular="Purchase_Order",
    plural="Purchase_Orders",
    fields=(
        FieldSpec("Subject", "string", required=True),
        FieldSpec("PO_Number", "string"),
        FieldSpec("Status", "picklist", picklist_values=("Draft", "Pending", "Approved", "Received", "Cancelled")),
        FieldSpec("Vendor_Name", "lookup", lookup_module="Accounts"),
        FieldSpec("Tracking_Number", "string"),
        FieldSpec("Grand_Total", "double"),
        FieldSpec("Description", "text"),
    ),
)

INVOICES = ModuleSpec(
    api_name="Invoices",
    singular="Invoice",
    plural="Invoices",
    fields=(
        FieldSpec("Subject", "string", required=True),
        FieldSpec("Invoice_Number", "string"),
        FieldSpec("Status", "picklist", picklist_values=("Draft", "Sent", "Paid", "Partially Paid", "Cancelled")),
        FieldSpec("Account_Name", "lookup", lookup_module="Accounts"),
        FieldSpec("Sales_Order", "lookup", lookup_module="Sales_Orders"),
        FieldSpec("Grand_Total", "double"),
        FieldSpec("Paid", "double"),
        FieldSpec("Balance", "double"),
        FieldSpec("Description", "text"),
    ),
)

CAMPAIGNS = ModuleSpec(
    api_name="Campaigns",
    singular="Campaign",
    plural="Campaigns",
    fields=(
        FieldSpec("Campaign_Name", "string", required=True),
        FieldSpec(
            "Type",
            "picklist",
            picklist_values=(
                "Conference",
                "Trade Show",
                "Public Relations",
                "Seminar",
                "Email",
                "Webinar",
                "Advertisement",
                "Partner",
                "Referral",
            ),
        ),
        FieldSpec("Status", "picklist", picklist_values=("Planned", "Active", "Inactive", "Completed")),
        FieldSpec("Start_Date", "date"),
        FieldSpec("End_Date", "date"),
        FieldSpec("Budget", "double"),
        FieldSpec("Actual_Cost", "double"),
        FieldSpec("Expected_Revenue", "double"),
        FieldSpec("Num_Sent", "integer"),
        FieldSpec("Description", "text"),
    ),
    related_lists={
        "Tasks": ("Tasks", "What_Id"),
    },
)

SOLUTIONS = ModuleSpec(
    api_name="Solutions",
    singular="Solution",
    plural="Solutions",
    fields=(
        FieldSpec("Solution_Title", "string", required=True),
        FieldSpec("Solution_Number", "string"),
        FieldSpec("Status", "picklist", picklist_values=("Draft", "Published", "Reviewed", "Rejected")),
        FieldSpec("Question", "text"),
        FieldSpec("Answer", "text"),
        FieldSpec("Category", "string"),
        FieldSpec("Publish_Date", "date"),
        FieldSpec("Description", "text"),
    ),
)

MODULES: dict[str, ModuleSpec] = {
    m.api_name: m
    for m in (
        LEADS,
        CONTACTS,
        ACCOUNTS,
        DEALS,
        TASKS,
        MEETINGS,
        CALLS,
        QUOTES,
        SALES_ORDERS,
        PURCHASE_ORDERS,
        INVOICES,
        CAMPAIGNS,
        SOLUTIONS,
        CASES,
        VISITS,
        PRODUCTS,
        LABOR_COSTS,
        SPARE_PARTS,
        CASE_ACTIONS,
    )
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
            "fields": [
                {
                    "api_name": f.api_name,
                    "type": f.type,
                    "required": f.required,
                    "picklist_values": list(f.picklist_values),
                    "lookup_module": f.lookup_module,
                    "read_only": f.read_only,
                }
                for f in spec.fields
            ],
            "required": [f.api_name for f in spec.required_fields()],
            "related_lists": list(spec.related_lists),
        }
        for name, spec in MODULES.items()
    }
