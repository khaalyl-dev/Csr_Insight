/**
 * Enums aligned with database schema (schema.dbml)
 */

export type UserRole = 'SITE_USER' | 'CORPORATE_USER';
export type PlanStatus = 'DRAFT' | 'SUBMITTED' | 'VALIDATED' | 'REJECTED' | 'LOCKED';
export type ActivityStatus = 'DRAFT' | 'IN_PROGRESS' | 'COMPLETED' | 'CANCELLED' | 'VALIDATED';
export type ValidationStatus = 'PENDING' | 'APPROVED' | 'REJECTED';
export type EntityType = 'PLAN' | 'ACTIVITY' | 'REALIZATION' | 'CHANGE_REQUEST';
export type PartnerType = 'NGO' | 'SCHOOL' | 'ASSOCIATION' | 'SUPPLIER' | 'GOVERNMENT' | 'OTHER';
export type OrganizationType = 'INTERNAL' | 'PARTNERSHIP';
export type ContractType = 'ONE_SHOT' | 'SUCCESSIVE_PERFORMANCE';
export type CollaborationNature = 'CHARITY_DONATION' | 'PARTNERSHIP' | 'SPONSORSHIP' | 'OTHERS';
