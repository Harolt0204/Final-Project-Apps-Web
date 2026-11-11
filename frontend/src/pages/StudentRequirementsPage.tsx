import { Link, useParams } from "react-router";
import RequirementsPanel from "../components/RequirementsPanel";

/** Admin view of one student's administrative requirements, reached from the student list. */
export default function StudentRequirementsPage() {
  const { id } = useParams();
  return (
    <>
      <p className="breadcrumb">
        <Link to="/students">Students</Link> › Requirements
      </p>
      <RequirementsPanel key={id} studentId={Number(id)} canEdit title="Administrative requirements" />
    </>
  );
}
