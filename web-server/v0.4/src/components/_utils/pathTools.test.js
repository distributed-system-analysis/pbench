import urlToList from './pathTools';

describe('test urlToList', () => {
  it('single path', () => {
    expect(urlToList('/dashboard')).toEqual(['/dashboard']);
  });
  it('secondary path', () => {
    expect(urlToList('/dashboard/results')).toEqual(['/dashboard', '/dashboard/results']);
  });
});
