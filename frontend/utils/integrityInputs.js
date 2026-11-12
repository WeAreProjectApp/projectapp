// BaseSelect emits strings: recover each option's declared type before sending.
export function integrityParams(inputs, values) {
  return Object.fromEntries(Object.entries(values).filter(([, value]) => value !== '').map(([key, value]) => {
    const field = inputs[key] || {}
    const option = field.options?.find((item) => String(item.value) === String(value))
    return [key, option ? option.value : field.type === 'integer' ? Number(value) : value]
  }))
}

export function integrityDestination(subject) {
  const routes = {
    'content.document': `/panel/documents/${subject.id}/edit`,
    'accounts.project': `/panel/projects?highlight=${subject.id}`,
    'accounts.userprofile': `/panel/clients?highlight=${subject.id}`,
    'content.businessproposal': `/panel/proposals/${subject.id}/edit`,
    'content.communicationthread': `/panel/communications?thread=${subject.id}`,
  }
  return routes[subject.model] || null
}
