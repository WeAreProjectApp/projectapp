export function issueError(error, fallback) {
  const data = error.response?.data
  if (typeof data?.detail === 'string') return data.detail
  const values = Object.values(data || {}).flat().filter((value) => typeof value === 'string')
  return values.join(' ') || fallback
}

export function issueSourcePayload(requirement) {
  if (!requirement) return {}
  return {
    source_requirement_id: requirement.id,
    ...(requirement.source_publication_id ? { source_publication_id: requirement.source_publication_id } : {}),
    ...(requirement.source_requirement_version != null ? { source_requirement_version: requirement.source_requirement_version } : {}),
  }
}

export function prefillIssueGuide(form, requirement) {
  const guide = requirement?.guide
  if (!guide) return
  if (!form.description?.trim()) form.description = [guide.preparation, guide.data].filter(Boolean).join('\n')
  if ('steps_to_reproduce' in form && form.steps_to_reproduce.every((step) => !step.trim()) && guide.steps?.length) {
    form.steps_to_reproduce = [...guide.steps]
  }
  if ('expected_behavior' in form && !form.expected_behavior?.trim()) form.expected_behavior = guide.expected_result || ''
  const environment = guide.environment?.toLowerCase().trim()
  if ('environment' in form && ['production', 'staging', 'dev'].includes(environment)) form.environment = environment
}
