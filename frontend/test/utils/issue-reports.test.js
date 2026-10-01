import { issueError, issueSourcePayload, prefillIssueGuide } from '../../utils/issue-reports'

const form = (overrides = {}) => ({ description: '', steps_to_reproduce: [''], expected_behavior: '', environment: 'production', ...overrides })
const requirement = (overrides = {}) => ({ id: 7, source_publication_id: 18, source_requirement_version: 3, guide: { preparation: 'Sign in', data: 'Record A', steps: ['Open', 'Save'], expected_result: 'Saved', environment: 'staging' }, ...overrides })

describe('Issue context', () => {
  it('carries the original publication into submission', () => {
    expect(issueSourcePayload(requirement())).toEqual({ source_requirement_id: 7, source_publication_id: 18, source_requirement_version: 3 })
  })

  it('omits context for a general report', () => {
    expect(issueSourcePayload(null)).toEqual({})
  })

  it('prefills reproduction instructions from a guide', () => {
    const value = form()
    prefillIssueGuide(value, requirement())
    expect(value.steps_to_reproduce).toEqual(['Open', 'Save'])
    expect(value.expected_behavior).toBe('Saved')
    expect(value.description).toBe('Sign in\nRecord A')
    expect(value.environment).toBe('staging')
  })

  it('preserves the reporter edited instructions', () => {
    const value = form({ description: 'Actual data B', steps_to_reproduce: ['Reporter step'], expected_behavior: 'Reporter result' })
    prefillIssueGuide(value, requirement())
    expect(value.description).toBe('Actual data B')
    expect(value.steps_to_reproduce).toEqual(['Reporter step'])
    expect(value.expected_behavior).toBe('Reporter result')
  })

  it('shows field validation errors from the API', () => {
    expect(issueError({ response: { data: { source_requirement_id: ['Unavailable guide.'] } } }, 'Fallback')).toBe('Unavailable guide.')
  })
})
