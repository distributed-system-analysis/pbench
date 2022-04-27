import { isValidDate } from "@patternfly/react-core"

export const formatDate=(date)=>{
    if (!isValidDate(date)) return;
    const dateWithoutOffset=date.toString().split(/\+|-/)
    return (new Date(dateWithoutOffset)).toISOString().split('T')[0]
}
