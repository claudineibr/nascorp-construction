class ConstructionFeature:
    PROJECTS = "construction_projects"
    UNITS = "construction_units"
    SCHEDULE = "construction_schedule"
    MEASUREMENTS = "construction_measurements"
    PROCUREMENT = "construction_procurement"
    REPORTS = "construction_reports"
    INSPECTION_VERDICT = "construction_inspection_verdict"
    MEASUREMENT_SELF_APPROVAL = "construction_measurement_self_approval"
    UNIT_TERMINATION = "construction_unit_termination"


class PermissionAction:
    READ = 1
    CREATE = 2
    UPDATE = 4
    DELETE = 8
    FULL = READ | CREATE | UPDATE | DELETE
