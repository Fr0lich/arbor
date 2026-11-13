"""backend/mobile_schemas.py - Declarative request validation schemas for Arbor Mobile Server."""

from __future__ import annotations

from marshmallow import Schema, fields, pre_load, EXCLUDE, ValidationError

DANGEROUS_STARTS = ("=", "+", "-", "@", "\t", "\r")


def sanitize_string_field(val: str | None) -> str:
    """Sanitize strings to prevent CSV/Excel injection formula triggers."""
    if not val:
        return ""
    s = str(val).strip()
    if s.startswith(DANGEROUS_STARTS):
        s = "'" + s
    return s


class ObjectUpdateSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    oid = fields.String(required=False, allow_none=True)
    id = fields.String(required=False, allow_none=True)
    reviewed = fields.Raw(required=False, allow_none=True)
    observation = fields.Dict(keys=fields.String(), values=fields.Raw(), required=False, allow_none=True)
    updates = fields.Dict(keys=fields.String(), values=fields.Raw(), required=False, allow_none=True)
    registration = fields.Dict(keys=fields.String(), values=fields.Raw(), required=False, allow_none=True)
    unvalidated_sources = fields.Raw(required=False, allow_none=True)
    unvalidated = fields.Raw(required=False, allow_none=True)
    timestamp = fields.Raw(required=False, allow_none=True)
    problem = fields.String(required=False, allow_none=True)
    problem_note = fields.String(required=False, allow_none=True)
    note = fields.String(required=False, allow_none=True)
    notes = fields.String(required=False, allow_none=True)

    @pre_load
    def normalize_fields(self, data, **kwargs):
        if not isinstance(data, dict):
            return {}
        # Unify 'id' vs 'oid'
        resolved_oid = str(data.get("id") or data.get("oid") or "").strip()
        data["oid"] = resolved_oid

        # Unify observation updates
        obs = data.get("observation") or data.get("updates") or {}
        if isinstance(obs, dict):
            obs_dict = {
                str(k): sanitize_string_field(v) if isinstance(v, str) else v
                for k, v in obs.items()
            }
        else:
            obs_dict = {}

        # Handle problem and note fields
        prob = data.get("problem")
        if prob:
            obs_dict[str(prob)] = True
        p_note = data.get("problem_note") or data.get("note") or data.get("notes")
        if p_note:
            note_val = sanitize_string_field(p_note)
            if prob:
                note_key = f"{prob}_Note" if not prob.endswith("_Note") else prob
                obs_dict[note_key] = note_val
            obs_dict["Notes"] = note_val

        data["observation"] = obs_dict

        # Unify registration updates
        reg = data.get("registration") or {}
        if isinstance(reg, dict):
            data["registration"] = {
                str(k): sanitize_string_field(v) if isinstance(v, str) else v
                for k, v in reg.items()
            }
        else:
            data["registration"] = {}

        # Unify unvalidated
        unval = data.get("unvalidated_sources")
        if unval is None:
            unval = data.get("unvalidated")
        data["unvalidated_sources"] = unval
        return data


class BatchUpdateSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    updates = fields.List(fields.Nested(ObjectUpdateSchema), required=True)


class BatchLocationUpdateSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    items = fields.List(fields.Raw(), required=False)
    object_ids = fields.List(fields.Raw(), required=False)
    location = fields.Dict(keys=fields.String(), values=fields.Raw(), required=False)
    timestamp = fields.Raw(required=False, allow_none=True)


class PresenceSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    oid = fields.String(required=False, allow_none=True)
    id = fields.String(required=False, allow_none=True)

    @pre_load
    def normalize_oid(self, data, **kwargs):
        if not isinstance(data, dict):
            return {}
        resolved_oid = str(data.get("oid") or data.get("id") or "").strip()
        data["oid"] = resolved_oid
        return data
